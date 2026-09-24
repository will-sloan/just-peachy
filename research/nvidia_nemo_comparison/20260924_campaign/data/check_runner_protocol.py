"""Non-inference lock/cache/resume checks against isolated evidence fixtures. See README.md."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

import psutil

from bind_corpus import Audit, check, load, save


def main(args):
    source, run = Path(args.source), Path(args.run)
    root = Path(args.local) / ("runner_protocol_" + uuid.uuid4().hex[:10])
    root.mkdir(parents=True)
    runner = Path(__file__).with_name("run_baseline_screen.py")
    admission = load(run / "ADMISSION.json")
    contract = admission["contract"]
    first_checkpoint = next(p for p in sorted((run / "cells").glob("*/CHECKPOINT.json")) if load(p)["status"] == "COMPLETE")
    checkpoint = load(first_checkpoint)
    check(Path(checkpoint["result"]["path"]).exists(), "A completed actual cell is required")
    before_result_sha = Audit().bind(checkpoint["result"])["sha256"]
    rows = []
    def invoke(name, prepare_fixture, expected_code, expected_text):
        target = root / name
        target.mkdir()
        prepare_fixture(target)
        command = [sys.executable, str(runner), "--source", str(source), "--manifest", contract["manifest"]["path"], "--models", str(Path(contract["models"][0]["path"]).parents[1]), "--output", str(target), "--prepare-only"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        output = result.stdout + result.stderr
        passed = result.returncode == expected_code and expected_text in output
        save(target / "CHECK_RECEIPT.json", {"command": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "pass": passed, "neural_inference_requested": False})
        rows.append({"case": name, "pass": passed, "exit_code": result.returncode, "expected_evidence": expected_text, "private_receipt": str(target / "CHECK_RECEIPT.json")})
        check(passed, name + " did not produce the required guard behavior")
        return target
    def lock_fixture(target):
        process = psutil.Process()
        save(target / "RUNNER_LOCK.json", {"pid": process.pid, "process_create_time": process.create_time(), "fixture": "This active test owns this isolated output; no real baseline lock is modified."})
    invoke("live_one_writer_lock", lock_fixture, 1, "live worker coordinator already owns this output")
    def bad_contract(target):
        value = json.loads(json.dumps(admission))
        value["contract_sha256"] = "0" * 64
        save(target / "ADMISSION.json", value)
    invoke("changed_contract_refused", bad_contract, 1, "Resume source/model/runtime/config/manifest binding changed")
    def copied_complete(target):
        save(target / "ADMISSION.json", admission)
        save(target / "cells" / first_checkpoint.parent.name / "CHECKPOINT.json", checkpoint)
    valid = invoke("completed_cell_resume", copied_complete, 0, '"jobs_pending": ' + str(len(load(contract["manifest"]["path"])["jobs"]) - 1))
    check(load(valid / "PROGRESS.json")["completed"] == 1, "Completed current N1 cell was not reused")
    def bad_result(target):
        copied_complete(target)
        value = json.loads(json.dumps(checkpoint))
        value["result"]["sha256"] = "0" * 64
        save(target / "cells" / first_checkpoint.parent.name / "CHECKPOINT.json", value)
    invoke("changed_result_hash_refused", bad_result, 1, "Checkpoint result changed")
    check(Audit().bind(checkpoint["result"])["sha256"] == before_result_sha, "Original N1 result changed")
    summary = {"status": "ACTUALLY_RUN_PASS_NONINFERENCE_PROTOCOL", "checks": rows, "neural_calls": 0, "hardware_calls": 0, "original_baseline_evidence_unchanged": True, "scope": "Isolated lock/contract/cache fixtures plus exact current N1 completed-cell evidence; does not simulate neural worker correctness", "private_fixture_root": str(root), "worker_failure_scope": "Actual worker-failure supervision tests are recorded separately by the supervisor; no active inference worker was killed by these tests."}
    save(Path(args.out) / "RUNNER_PROTOCOL_RECEIPT.json", summary)
    print(json.dumps({"status": summary["status"], "checks": len(rows), "all_pass": all(r["pass"] for r in rows)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--local", default=r"G:\Just_Peachy_N1\20260924_campaign\local\data")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent))
    main(parser.parse_args())
