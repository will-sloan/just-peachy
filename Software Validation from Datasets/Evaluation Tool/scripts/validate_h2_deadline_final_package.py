"""Independently validate the H2 deadline-bounded final result package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from app.full_pipeline_evaluation.results import validate_result_tree  # noqa: E402


REQUIRED_SUMMARY_FILES = (
    "FINAL_STATUS.json",
    "FINAL_PIPELINE_REPORT.md",
    "FINAL_PIPELINE_RANKING.csv",
    "DEADLINE_PANEL_ALL_METRICS.csv",
    "DEADLINE_PANEL_CRITICAL_METRICS.csv",
    "DEADLINE_PANEL_BOOTSTRAP_INTERVALS.csv",
    "DEADLINE_PANEL_RESULT_INVENTORY.csv",
    "DEADLINE_PANEL_FAILURES.csv",
    "DEADLINE_PANEL_METRIC_GUIDE.md",
    "REPRODUCIBILITY_MANIFEST.json",
    "RESULT_FILE_INVENTORY.csv",
    "H2_TIMEBOXED_FINAL_RESULTS.zip",
    "UPLOAD_THIS_FILE_TO_CHATGPT.txt",
    "DEADLINE_BOUNDED_HELDOUT_PLAN.json",
    "DEADLINE_PANEL_CASES.jsonl",
    "DEADLINE_MEMORY_RETRY_RECEIPT.json",
    "DEADLINE_DIRECT_KNOWN_RETRY_RECEIPT.json",
    "DEADLINE_FINALIZER_LOW_IO_RESTART_RECEIPT.json",
    "HELDOUT_EXECUTION_MANIFEST.json",
    "COMMON_APP_TARGETED_VALIDATION.json",
    "DEADLINE_HOST_INTERFERENCE_OBSERVATION.json",
    "ARM64_WHEEL_RESOLUTION_RECEIPT.json",
    "ARM64_HARDWARE_ASSESSMENT.md",
    "FINAL_COMPLETION_AUDIT.md",
    "DEADLINE_OPERATIONAL_RECOVERY_AND_LIMITATIONS.md",
    "DETAILED_RESULT_INTERPRETATION.md",
    "FINAL_ANALYSIS_METRICS.csv",
    "validate_h2_deadline_final_package.py",
    "H2_DEADLINE_FINAL_PACKAGE_VALIDATION_README.md",
)
FORBIDDEN_SUFFIXES = {
    ".bin",
    ".engine",
    ".gguf",
    ".mlmodel",
    ".onnx",
    ".pt",
    ".pth",
    ".ckpt",
    ".safetensors",
    ".wav",
    ".flac",
    ".mp3",
    ".npz",
    ".npy",
    ".tflite",
}
FORBIDDEN_PATH_TOKENS = (
    "biometric",
    "credential",
    "embedding_cache",
    "model_cache",
    "raw_dataset",
    "secret",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def complete_case_ids(result: Path) -> list[str]:
    status = result / "diagnostics/case_status.jsonl"
    rows: list[str] = []
    with status.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip():
                continue
            value = json.loads(line)
            if str(value.get("status") or "").casefold() == "complete":
                rows.append(str(value["case_id"]))
    return rows


def validate(args: argparse.Namespace) -> dict[str, object]:
    workspace = Path(args.workspace).resolve()
    summary = Path(args.summary_root).resolve()
    missing = [name for name in REQUIRED_SUMMARY_FILES if not (summary / name).is_file()]
    if missing:
        raise RuntimeError(f"required final files are missing: {missing}")

    plan = read_json(workspace / "timeboxed_completion/deadline_bounded_heldout_plan.json")
    packaged_plan = read_json(summary / "DEADLINE_BOUNDED_HELDOUT_PLAN.json")
    if plan != packaged_plan:
        raise RuntimeError("packaged deadline plan differs from the frozen workspace plan")
    expected = [str(value) for value in plan["selected_case_ids"]]
    if len(expected) != args.expected_case_count:
        raise RuntimeError("the frozen plan has an unexpected case count")

    status = read_json(summary / "FINAL_STATUS.json")
    if status.get("status") != "COMPLETE_H2_DEADLINE_BOUNDED_RESULTS":
        raise RuntimeError(f"final status is not complete: {status.get('status')}")
    if int(status.get("case_count_per_mode") or 0) != len(expected):
        raise RuntimeError("FINAL_STATUS case count differs from the frozen plan")

    direct_retry_source = (
        workspace / "timeboxed_completion/deadline_direct_known_retry_result.json"
    )
    direct_retry = read_json(direct_retry_source)
    packaged_direct_retry = read_json(
        summary / "DEADLINE_DIRECT_KNOWN_RETRY_RECEIPT.json"
    )
    if direct_retry != packaged_direct_retry:
        raise RuntimeError("packaged direct known-only retry receipt differs")
    unsigned_retry = dict(direct_retry)
    claimed_retry_sha = unsigned_retry.pop("receipt_sha256", None)
    if claimed_retry_sha != canonical_sha256(unsigned_retry):
        raise RuntimeError("direct known-only retry receipt checksum differs")
    if not (
        direct_retry.get("status") == "TARGET_REACHED"
        and int(direct_retry.get("completed_cases") or 0) == len(expected)
        and direct_retry.get("plan_sha256") == plan.get("receipt_sha256")
        and direct_retry.get("scientific_settings_changed") is False
        and direct_retry.get("metrics_inspected_for_recovery") is False
        and direct_retry.get("queue_state") == "stopped"
        and direct_retry.get("job_identity_sha256")
        in set(plan.get("source_execution_job_identity_sha256") or [])
    ):
        raise RuntimeError("direct known-only retry receipt is not acceptable")
    known_attempt_root = (
        workspace
        / "heldout_frozen_queue/attempts"
        / str(direct_retry["job_id"])
    ).resolve()

    result_rows = read_csv(summary / "DEADLINE_PANEL_RESULT_INVENTORY.csv")
    if len(result_rows) != 2:
        raise RuntimeError("the result inventory must contain exactly two H2 modes")
    results: list[dict[str, object]] = []
    for row in result_rows:
        root = Path(row["result_root"]).resolve()
        validation = validate_result_tree(root)
        completed = complete_case_ids(root)
        if not validation.valid:
            raise RuntimeError(f"result tree is not valid: {root}")
        if completed != expected:
            raise RuntimeError(f"result cases differ from the frozen order: {root}")
        deadline_stopped_prefix = bool(
            row.get("mode") == "H2_KNOWN_ONLY"
            and row.get("run_status") == "stopped"
            and root.is_relative_to(known_attempt_root)
            and isinstance(direct_retry.get("outcome"), dict)
            and direct_retry["outcome"].get("result_valid") is True
        )
        if not validation.reusable and not deadline_stopped_prefix:
            raise RuntimeError(
                f"non-reusable result lacks the exact deadline-prefix receipt: {root}"
            )
        if int(row["completed_case_count"]) != len(expected):
            raise RuntimeError(f"result inventory count differs: {root}")
        if sha256_file(root / "checksums.json") != row["checksums_sha256"]:
            raise RuntimeError(f"result inventory checksum differs: {root}")
        results.append(
            {
                "job_id": row["job_id"],
                "mode": row["mode"],
                "result_root": str(root),
                "checksums_sha256": row["checksums_sha256"],
                "result_reusable": validation.reusable,
                "accepted_deadline_stopped_prefix": deadline_stopped_prefix,
            }
        )

    all_metrics = read_csv(summary / "DEADLINE_PANEL_ALL_METRICS.csv")
    if not all_metrics:
        raise RuntimeError("all-metrics table is empty")
    job_ids = {str(row["job_id"]) for row in result_rows}
    metric_job_ids = {row["job_id"] for row in all_metrics}
    if not job_ids.issubset(metric_job_ids):
        raise RuntimeError("all-metrics table omits a retained mode")
    punctuation = [
        row for row in all_metrics if row["metric_id"] == "punctuation_insensitive_wer"
    ]
    if len(punctuation) != 2 or {row["job_id"] for row in punctuation} != job_ids:
        raise RuntimeError("punctuation-insensitive WER is not present for both modes")
    if any(row["status"] not in {"computed", "undefined"} for row in punctuation):
        raise RuntimeError("punctuation-insensitive WER has an invalid status")

    critical = read_csv(summary / "DEADLINE_PANEL_CRITICAL_METRICS.csv")
    if len(critical) != 2 or {row["job_id"] for row in critical} != job_ids:
        raise RuntimeError("critical-metrics table does not cover both modes")
    bootstrap = read_csv(summary / "DEADLINE_PANEL_BOOTSTRAP_INTERVALS.csv")
    if not bootstrap:
        raise RuntimeError("speaker-cluster bootstrap table is empty")
    reproducibility = read_json(summary / "REPRODUCIBILITY_MANIFEST.json")
    bootstrap_spec = reproducibility.get("bootstrap")
    if not isinstance(bootstrap_spec, dict):
        raise RuntimeError("reproducibility manifest omits bootstrap settings")
    if bootstrap_spec.get("repetitions") != 2000 or bootstrap_spec.get("seed") != 3800:
        raise RuntimeError("bootstrap settings differ from the frozen plan")

    zip_path = summary / "H2_TIMEBOXED_FINAL_RESULTS.zip"
    zip_sha = sha256_file(zip_path)
    pointer = (summary / "UPLOAD_THIS_FILE_TO_CHATGPT.txt").read_text(
        encoding="utf-8-sig"
    )
    if str(zip_path) not in pointer or zip_sha not in pointer:
        raise RuntimeError("upload pointer does not bind the current ZIP")

    inventory = read_csv(summary / "RESULT_FILE_INVENTORY.csv")
    if not inventory:
        raise RuntimeError("result file inventory is empty")
    if any(row["relative_path"] == "RESULT_FILE_INVENTORY.csv" for row in inventory):
        raise RuntimeError("result inventory contains an unverifiable self-hash")

    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC validation failed: {bad}")
        names = set(archive.namelist())
        forbidden = sorted(
            name
            for name in names
            if Path(name).suffix.casefold() in FORBIDDEN_SUFFIXES
            or any(token in name.casefold() for token in FORBIDDEN_PATH_TOKENS)
        )
        if forbidden:
            raise RuntimeError(f"forbidden large/sensitive payloads are packaged: {forbidden}")
        inventoried_names = {row["relative_path"] for row in inventory}
        expected_zip_names = inventoried_names | {"RESULT_FILE_INVENTORY.csv"}
        if names != expected_zip_names:
            raise RuntimeError(
                "ZIP membership differs from the complete inventory coverage: "
                f"extra={sorted(names - expected_zip_names)}, "
                f"missing={sorted(expected_zip_names - names)}"
            )
        if archive.read("RESULT_FILE_INVENTORY.csv") != (
            summary / "RESULT_FILE_INVENTORY.csv"
        ).read_bytes():
            raise RuntimeError("ZIP inventory bytes differ from the disk inventory")
        for row in inventory:
            relative = row["relative_path"]
            disk = summary / relative
            if not disk.is_file():
                raise RuntimeError(f"inventoried disk file is missing: {relative}")
            if relative not in names:
                raise RuntimeError(f"inventoried ZIP member is missing: {relative}")
            disk_sha = sha256_file(disk)
            zip_bytes = archive.read(relative)
            if int(row["bytes"]) != disk.stat().st_size:
                raise RuntimeError(f"inventoried byte count differs: {relative}")
            if row["sha256"] != disk_sha or row["sha256"] != sha256_bytes(zip_bytes):
                raise RuntimeError(f"inventoried checksum differs: {relative}")

    copied_sources = {
        "DEADLINE_BOUNDED_HELDOUT_PLAN.json": workspace
        / "timeboxed_completion/deadline_bounded_heldout_plan.json",
        "DEADLINE_MEMORY_RETRY_RECEIPT.json": workspace
        / "timeboxed_completion/deadline_memory_retry_receipt.json",
        "DEADLINE_DIRECT_KNOWN_RETRY_RECEIPT.json": direct_retry_source,
        "DEADLINE_FINALIZER_LOW_IO_RESTART_RECEIPT.json": workspace
        / "timeboxed_completion/deadline_finalizer_low_io_restart_receipt.json",
        "DEADLINE_PANEL_CASES.jsonl": workspace
        / "timeboxed_completion/deadline_panel_cases.jsonl",
        "HELDOUT_EXECUTION_MANIFEST.json": workspace / "heldout_execution_manifest.json",
        "ARM64_WHEEL_RESOLUTION_RECEIPT.json": workspace
        / "storage_maintenance/arm64_wheel_resolution_receipt.json",
        "COMMON_APP_TARGETED_VALIDATION.json": Path(str(plan["results_root"]))
        / "jobs/h2p6_h2_current_common_app_targeted_validation_634db2b15e/artifacts/job_result.json",
        "DEADLINE_HOST_INTERFERENCE_OBSERVATION.json": workspace
        / "engineering_validation/deadline_host_interference_observation.json",
    }
    for packaged_name, source in copied_sources.items():
        if sha256_file(summary / packaged_name) != sha256_file(source):
            raise RuntimeError(f"packaged receipt differs from its source: {packaged_name}")

    return {
        "schema_version": "h2-deadline-final-package-validation.v1",
        "status": "PASS",
        "case_count_per_mode": len(expected),
        "result_count": len(results),
        "results": results,
        "all_metric_rows": len(all_metrics),
        "bootstrap_rows": len(bootstrap),
        "inventory_rows_verified": len(inventory),
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--expected-case-count", type=int, default=24)
    parser.add_argument("--receipt")
    args = parser.parse_args()
    receipt = validate(args)
    if args.receipt:
        target = Path(args.receipt).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
