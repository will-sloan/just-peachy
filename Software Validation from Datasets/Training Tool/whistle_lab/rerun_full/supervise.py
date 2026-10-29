"""One sequential full-training trajectory with finite exact recovery."""
from __future__ import annotations
import subprocess
import sys
import time
import traceback
from runtime import *
from policy import select


def main():
    import fcntl
    lock = (RUN/"supervisor.lock").open("a+b")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return 73
    try:
        return pipeline(lock)
    finally:
        lock.close()


def pipeline(lock):
    config = verify()
    if read_json(RUN/"summary.json").get("complete"):
        return 0
    if paused():
        status("paused", message="User pause is active")
        return 75
    recovery = read_json(RUN/"recovery.json")
    recovery.setdefault("attempts", {})
    recovery.setdefault("history", [])

    def run(script, args, key):
        if recovery["attempts"].get(key, 0) >= 3:
            raise RuntimeError("Finite retry limit reached for " + key)
        while True:
            if paused():
                return 75
            status("starting_stage", stage=key, message="Starting " + key)
            process = subprocess.Popen([sys.executable, "-u", str(SOURCE/script), *args],
                                       pass_fds=(lock.fileno(),))
            atomic_json(RUN/"worker.json", {"pid": process.pid, "script": script, "args": args,
                                          "stage": key, "started_at": time.time()})
            code = process.wait()
            if code in (0, 73, 75):
                return code
            recovery["attempts"][key] = recovery["attempts"].get(key, 0)+1
            recovery["history"].append({"stage": key, "exit_code": code, "time": time.time(),
                                       "checkpoint_step": read_json(RUN/"checkpoint.json").get("step")})
            atomic_json(RUN/"recovery.json", recovery)
            if recovery["attempts"][key] >= 3:
                raise RuntimeError("Finite retry limit reached for " + key)
            time.sleep(5)

    baseline = read_json(scores_path(0))
    if not baseline.get("complete"):
        code = run("score.py", ["0"], "initial_development")
        if code:
            return code
        baseline = read_json(scores_path(0))
    observed = []
    for target in config["validation_steps"]:
        checkpoint = read_json(RUN/"checkpoint.json")
        receipt = read_json(RUN/"exports"/f"step_{target:07d}.json")
        if not receipt.get("complete"):
            if checkpoint.get("step", 0) > target:
                raise ValueError("A required earlier export is missing; refuse an extra/restarted trajectory")
            code = run("worker.py", ["--target", str(target)], "training_to_"+str(target))
            if code:
                return code
            receipt = read_json(RUN/"exports"/f"step_{target:07d}.json")
        summary = read_json(scores_path(target))
        if not summary.get("complete"):
            code = run("score.py", [str(target)], "development_"+str(target))
            if code:
                return code
            summary = read_json(scores_path(target))
        if summary.get("model_sha256") != receipt.get("model_sha256"):
            raise ValueError("Score/export identities differ")
        from results import annotate
        uncertainty = annotate(target)
        observed.append((target, summary))
        chosen = select(baseline, observed, config["validation_steps"])
        existing_rows = read_json(RUN/"validation_summary.json").get("candidates", [])
        rows = [r for r in existing_rows if r["step"] < target]
        rows.append({"step": target, "exposure": receipt, "summary": summary, "uncertainty": uncertainty})
        atomic_json(RUN/"validation_summary.json", {"complete": False, "reference": baseline,
                    "candidates": rows, "selection": chosen, "planned_validations": 6})
    if not read_json(RUN/"checkpoint.json").get("training_cap_reached"):
        raise ValueError("All three full passes must finish before final selection")
    chosen = select(baseline, observed, config["validation_steps"])
    chosen.update(frozen=True, frozen_at=time.time(), independent_confirmation=False,
                  stop_reason="three complete passes; all six frozen validations completed")
    existing = read_json(RUN/"development_decision.json")
    if existing and existing["selected_step"] != chosen["selected_step"]:
        raise ValueError("Frozen development candidate changed")
    if existing:
        chosen = existing
    else:
        atomic_json(RUN/"development_decision.json", chosen)
    validation = read_json(RUN/"validation_summary.json")
    validation.update(complete=True, selection=chosen)
    atomic_json(RUN/"validation_summary.json", validation)
    if chosen["selected_step"]:
        for step in (0, chosen["selected_step"]):
            if not read_json(scores_path(step, "confirmation")).get("complete"):
                code = run("score.py", [str(step), "--role", "confirmation"], "confirmation_"+str(step))
                if code:
                    return code
    from results import finish
    finish(chosen)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        status("failed", message=str(error), traceback=traceback.format_exc())
        raise
