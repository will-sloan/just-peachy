"""One owned sequential pipeline; bounded retries and no extra trials."""
from __future__ import annotations
import json
import subprocess
import sys
import time
import traceback
from runtime import *
from policy import select


def candidates():
    rows = []
    for path in sorted((RUN / "exports").glob("step_*.json")):
        record = read_json(path)
        step = int(record["step"])
        summary = read_json(scores_path(step))
        if step and summary.get("complete"):
            rows.append((step, record["distinct_sources"].get("ami", 0), summary))
    return rows


def main():
    import fcntl
    lock = (RUN / "supervisor.lock").open("a+b")
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
    verify()
    if read_json(RUN / "summary.json").get("complete"):
        return 0
    if paused():
        status("paused", message="User pause is active")
        return 75
    recovery = read_json(RUN / "recovery.json")
    recovery.setdefault("attempts", {})
    recovery.setdefault("history", [])

    def run(script, args, key):
        if recovery["attempts"].get(key, 0) >= 3:
            raise RuntimeError("Finite retry limit reached for " + key)
        while True:
            if paused():
                return 75
            status("starting_stage", stage=key, message="Starting " + key)
            # Inherit the supervisor lock: an orphan child retains ownership until
            # it exits, so a replacement supervisor cannot launch a duplicate.
            process = subprocess.Popen([sys.executable, "-u", str(SOURCE/script), *args],
                                       pass_fds=(lock.fileno(),))
            atomic_json(RUN/"worker.json", {"pid": process.pid, "script": script, "args": args,
                                           "stage": key, "started_at": time.time()})
            code = process.wait()
            if code in (0, 73, 75):
                return code
            recovery["attempts"][key] = recovery["attempts"].get(key, 0) + 1
            recovery["history"].append({"stage": key, "exit_code": code, "time": time.time(),
                                         "checkpoint_step": read_json(RUN/"checkpoint.json").get("step")})
            atomic_json(RUN/"recovery.json", recovery)
            if recovery["attempts"][key] >= 3:
                raise RuntimeError("Finite retry limit reached for " + key)
            time.sleep(5)

    if not (read_json(RUN/"initialization_verification.json").get("passed") and read_json(RUN/"preflight.json").get("complete")):
        code = run("worker.py", ["--initialize"], "initialize")
        if code:
            return code
    code = run("score.py", ["0"], "development_0") if not read_json(scores_path(0)).get("complete") else 0
    if code:
        return code
    baseline = read_json(scores_path(0))
    while True:
        observed = candidates()
        chosen = select(baseline, observed)
        atomic_json(RUN/"validation_summary.json", {"complete": False, "reference": baseline,
            "candidates": [{"step": step, "distinct_ami_sources": count, "summary": summary}
                           for step, count, summary in observed], "selection": chosen})
        checkpoint = read_json(RUN/"checkpoint.json")
        step = checkpoint.get("step", 0)
        # A saved/exported block may still need scoring after an interruption.
        receipt = read_json(RUN/"exports"/f"step_{step:05d}.json")
        boundary = bool(receipt.get("complete") or checkpoint.get("training_cap_reached") or (step and step % 2000 == 0))
        if step > 0 and boundary and not read_json(scores_path(step)).get("complete"):
            if not receipt.get("complete"):
                code = run("worker.py", ["--target", str(step)], "export_" + str(step))
                if code:
                    return code
            code = run("score.py", [str(step)], "development_" + str(step))
            if code:
                return code
            continue
        if chosen["early_stop"] or checkpoint.get("training_cap_reached") or len(observed) >= 5:
            chosen.update(frozen=True, frozen_at=time.time(), independent_confirmation=False,
                          stop_reason=chosen["stop_reason"] or "fixed training/validation cap")
            existing = read_json(RUN/"development_decision.json")
            if existing and existing["selected_step"] != chosen["selected_step"]:
                raise ValueError("Previously frozen candidate changed")
            if not existing:
                atomic_json(RUN/"development_decision.json", chosen)
            else:
                chosen = existing
            validation = read_json(RUN/"validation_summary.json")
            validation.update(complete=True, selection=chosen)
            atomic_json(RUN/"validation_summary.json", validation)
            if chosen["selected_step"]:
                for number in (0, chosen["selected_step"]):
                    if not read_json(scores_path(number, "confirmation")).get("complete"):
                        code = run("score.py", [str(number), "--role", "confirmation"], "confirmation_" + str(number))
                        if code:
                            return code
            from results import finish
            finish(chosen)
            return 0
        target = min(10000, (step // 2000 + 1) * 2000)
        code = run("worker.py", ["--target", str(target)], "training_to_" + str(target))
        if code:
            return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        status("failed", message=str(error), traceback=traceback.format_exc())
        raise
