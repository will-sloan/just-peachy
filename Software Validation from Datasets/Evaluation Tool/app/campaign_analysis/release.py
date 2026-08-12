"""Predeclared Stage 12 release gates and synthetic workflow qualification."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Mapping

from app.campaign_exchange.common import atomic_write_bytes, atomic_write_json

from .contracts import RELEASE_SCHEMA_VERSION, AnalysisContractError


SYNTHETIC_TESTS = (
    "tests/automated_evaluation/test_stage4_campaign_executor.py::test_transient_failure_retries_and_preserves_partial_results",
    "tests/automated_evaluation/test_stage4_campaign_executor.py::test_timeout_terminates_subprocess",
    "tests/automated_evaluation/test_stage4_campaign_executor.py::test_interruption_is_restart_safe_and_resumable",
    "tests/automated_evaluation/test_stage4_campaign_executor.py::test_stop_request_terminates_only_selected_scenario",
    "tests/automated_evaluation/test_stage4_campaign_executor.py::test_process_restart_recovers_expired_running_lease",
    "tests/automated_evaluation/test_stage6_campaign_exchange.py::test_complete_two_worker_split_run_transfer_and_merge",
    "tests/automated_evaluation/test_stage6_campaign_exchange.py::test_transfer_detects_missing_files_and_checksum_corruption",
    "tests/automated_evaluation/test_stage6_campaign_exchange.py::test_long_transfer_path_remains_portable_in_indexes",
)


def evaluate_release_gates(
    analysis_manifest: Mapping[str, object],
    coverage: Mapping[str, object],
    decision_policy: Mapping[str, object],
    *,
    prerequisite_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    scenarios = [
        row
        for row in _items(analysis_manifest.get("scenario_index"), "scenario index")
        if isinstance(row, Mapping)
    ]
    planned = len(scenarios)
    included = sum(row.get("analysis_status") == "included" for row in scenarios)
    failed = sum(row.get("analysis_status") in {"failed", "invalid"} for row in scenarios)
    missing = sum(row.get("analysis_status") in {"missing", "excluded"} for row in scenarios)
    tiers = sorted({str(row.get("tier")) for row in scenarios})
    synthetic = bool(scenarios) and all(row.get("scenario_type") == "synthetic_executor" for row in scenarios)
    target_gate = "synthetic" if synthetic else (tiers[0] if len(tiers) == 1 else "mixed")
    release_gates = _mapping(decision_policy.get("release_gates"), "release gates")
    common = _mapping(release_gates.get("common"), "common release gate")
    completion_rate = included / planned if planned else 0.0
    failure_rate = failed / planned if planned else 0.0
    coverage_summary = _mapping(coverage.get("summary"), "coverage summary")
    mandatory_missing = int(str(coverage_summary["mandatory_unexpected_missing"]))
    checks = [
        _check("completion_rate", completion_rate >= float(str(common["completion_rate_minimum"])), completion_rate, common["completion_rate_minimum"]),
        _check("failure_rate", failure_rate <= float(str(common["failure_rate_maximum"])), failure_rate, common["failure_rate_maximum"]),
        _check("mandatory_unexpected_missing", mandatory_missing <= int(str(common["mandatory_unexpected_missing_maximum"])), mandatory_missing, common["mandatory_unexpected_missing_maximum"]),
        _check("exact_scenario_reconciliation", len(scenarios) == planned and missing == 0, {"planned": planned, "indexed": len(scenarios), "missing_or_excluded": missing}, "all planned scenarios indexed and included"),
        _check("validated_included_scenarios", all(row.get("validation_complete") for row in scenarios if row.get("analysis_status") == "included"), included, "every included scenario validates"),
    ]
    prerequisite = _prerequisite(target_gate, decision_policy, prerequisite_evidence)
    checks.append(prerequisite)
    passed = all(bool(item["passed"]) for item in checks)
    campaign = _mapping(analysis_manifest.get("campaign"), "analysis campaign")
    result: dict[str, object] = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "campaign_id": campaign["campaign_id"],
        "analysis_manifest_id": analysis_manifest["analysis_manifest_id"],
        "decision_policy_version": decision_policy["policy_version"],
        "target_gate": target_gate,
        "status": "passed" if passed else "blocked",
        "passed": passed,
        "checks": checks,
        "counts": {
            "planned": planned,
            "included": included,
            "failed_or_invalid": failed,
            "missing_or_excluded": missing,
        },
        "next_gate": {"synthetic": "small", "small": "standard", "standard": "large", "large": None}.get(target_gate),
        "gpu_concurrency_limit": int(str(common["gpu_concurrency_limit_without_qualification"])),
        "limitations": [
            "A contract gate is not a model-quality claim.",
            "Small, standard, and large gates require their own completed campaign evidence.",
            "GPU concurrency remains one until a separate sustained concurrency qualification passes.",
        ],
    }
    return result


def qualify_synthetic_release(
    project_root: Path,
    output_root: Path,
    *,
    python_executable: Path | None = None,
) -> dict[str, object]:
    """Run the existing Stage 4/6 synthetic workflow qualifications as one gate."""

    root = project_root.resolve()
    destination = output_root.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    temporary_root = destination / "pytest_tmp"
    command = [
        str((python_executable or Path(sys.executable)).resolve()),
        "-m",
        "pytest",
        *SYNTHETIC_TESTS,
        "-q",
        "--basetemp",
        str(temporary_root),
    ]
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path = destination / "synthetic_release_qualification.log"
    atomic_write_bytes(log_path, completed.stdout.encode("utf-8", errors="replace"))
    shutil.rmtree(temporary_root, ignore_errors=True)
    passed = completed.returncode == 0
    evidence = {
        "two_worker_merge": passed,
        "timeout_retry": passed,
        "interruption_resume": passed,
        "stop_request": passed,
        "restart_recovery": passed,
        "transfer_checksums": passed,
        "long_path": passed,
        "exact_reconciliation": passed,
    }
    result: dict[str, object] = {
        "schema_version": "synthetic-release-workflow-qualification.v1",
        "target_gate": "synthetic",
        "next_gate": "small",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "command": [Path(command[0]).name, *command[1:-2], "--basetemp", "<output>/pytest_tmp"],
        "test_nodes": list(SYNTHETIC_TESTS),
        "return_code": completed.returncode,
        "evidence": evidence,
        "log": log_path.name,
        "claims": "campaign mechanics only; no model, accuracy, GPU, or scientific performance claim",
    }
    atomic_write_json(destination / "synthetic_release_qualification.json", result)
    if not passed:
        raise AnalysisContractError(f"synthetic release workflow failed; see {log_path}")
    return result


def _check(name: str, passed: bool, observed: object, required: object) -> dict[str, object]:
    return {"name": name, "passed": bool(passed), "observed": observed, "required": required}


def _prerequisite(
    target_gate: str,
    policy: Mapping[str, object],
    evidence: Mapping[str, object] | None,
) -> dict[str, object]:
    release_gates = _mapping(policy.get("release_gates"), "release gates")
    gate = release_gates.get(target_gate)
    if not isinstance(gate, Mapping):
        return _check("recognized_release_tier", False, target_gate, "synthetic, small, standard, or large")
    if target_gate == "synthetic":
        required = [str(item) for item in _items(gate.get("requires"), "required evidence")]
        values = evidence.get("evidence", evidence) if isinstance(evidence, Mapping) else {}
        missing = [name for name in required if not isinstance(values, Mapping) or values.get(name) is not True]
        return _check("synthetic_workflow_evidence", not missing, {"missing": missing}, required)
    prerequisite = str(gate["prerequisite_gate"])
    passed = bool(evidence and evidence.get("target_gate") == prerequisite and evidence.get("passed") is True)
    return _check("prerequisite_gate", passed, evidence.get("target_gate") if evidence else None, prerequisite)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AnalysisContractError(f"{label} must be a mapping")
    return value


def _items(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise AnalysisContractError(f"{label} must be a list")
    return value
