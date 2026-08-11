"""Materialize and run the credential-free production release hierarchy.

This is the high-level implementation behind ``scripts/run_release_gates.ps1``
and worker setup.  It composes existing immutable scenario catalogs, campaign
execution, artifact validation, transfer/merge, and Stage 12 analysis.  It does
not create a second evaluator and never downloads a model during inference.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Mapping, Sequence

import yaml


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
CONFIG_PATH = (
    TOOL_ROOT / "configs" / "automated_evaluation" / "production_release.v1.yaml"
)
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.artifact_contracts.atomic import file_sha256  # noqa: E402
from app.artifact_contracts.registry import (  # noqa: E402
    LATEST_ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
)
from app.campaign_analysis.analysis import analyze_campaign  # noqa: E402
from app.campaign_analysis.release import qualify_synthetic_release  # noqa: E402
from app.campaign_exchange import (  # noqa: E402
    create_worker_assignment,
    current_git_commit,
    export_worker_results,
    merge_worker_results,
    run_worker_assignment,
    validate_merged_results,
    validate_worker_assignment,
    validate_worker_transfer,
)
from app.campaign_exchange.common import atomic_write_json  # noqa: E402
from app.campaign_executor.planner import plan_campaign, validate_campaign  # noqa: E402
from app.campaign_executor.state import CampaignStateStore  # noqa: E402
from app.utils.json_utils import read_jsonl  # noqa: E402
from scripts.materialize_launch_campaign import materialize as materialize_massive  # noqa: E402


class ProductionReleaseError(RuntimeError):
    """Raised when a production release contract cannot be satisfied."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)

    materialize = actions.add_parser(
        "materialize", help="materialize the selected massive launch campaign"
    )
    _device(materialize)
    materialize.add_argument(
        "--machine-id", choices=("machine_a", "machine_b"), required=True
    )
    materialize.add_argument("--bind-current-commit", action="store_true")

    gates = actions.add_parser(
        "run-gates", help="run canary, small, and standard gates in order"
    )
    _device(gates)
    gates.add_argument(
        "--through", choices=("canary", "small", "standard", "all"), default="all"
    )

    gate = actions.add_parser("run-gate", help="run one declared production gate")
    _device(gate)
    gate.add_argument("--gate", choices=("canary", "small", "standard"), required=True)

    rehearsal = actions.add_parser(
        "materialize-rehearsal", help="materialize the bounded massive rehearsal"
    )
    _device(rehearsal)
    rehearsal_run = actions.add_parser(
        "run-rehearsal", help="run the bounded rehearsal through the campaign executor"
    )
    _device(rehearsal_run)
    rehearsal_run.add_argument("--resume-stopped", action="store_true")
    rehearsal_run.add_argument("--max-scenarios", type=int, default=None)
    rehearsal_finalize = actions.add_parser(
        "finalize-rehearsal",
        help="export, validate, merge, and analyze a completed bounded rehearsal",
    )
    _device(rehearsal_finalize)
    return parser


def _device(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", choices=("cpu", "cuda"), required=True)


def load_contract(path: Path = CONFIG_PATH) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "production-release.v1":
        raise ProductionReleaseError("unsupported production release contract")
    scope = _mapping(value.get("production_scope"), "production scope")
    if scope.get("credentials_required") != []:
        raise ProductionReleaseError("production scope may not require credentials")
    active = json.dumps(scope.get("active_components"), sort_keys=True).lower()
    for forbidden in _items(
        scope.get("excluded_optional_backends"), "excluded optional backends"
    ):
        if str(forbidden).lower() in active:
            raise ProductionReleaseError(
                f"excluded optional backend entered production scope: {forbidden}"
            )
    return value


def materialize_launch(
    device: str,
    machine_id: str,
    *,
    bind_current_commit: bool,
) -> dict[str, object]:
    contract = load_contract()
    campaign = _mapping(_mapping(contract["campaigns"], "campaigns")["massive"], "massive")
    package = TOOL_ROOT / str(_mapping(campaign["launch_packages"], "launch packages")[device])
    report = materialize_massive(
        package,
        TOOL_ROOT / "automated_runs",
        bind_current_commit=bind_current_commit,
    )
    _validate_required_assets(contract)
    report["production_scope"] = {
        "credentials_required": [],
        "excluded_optional_backends": _mapping(
            contract["production_scope"], "production scope"
        )["excluded_optional_backends"],
    }
    report["device_mode"] = device
    selected = _mapping(_mapping(report["assignments"], "assignments")[machine_id], machine_id)
    report["selected_worker"] = {
        "machine_id": machine_id,
        "assignment_id": selected["assignment_id"],
        "assignment_sha256": selected["assignment_sha256"],
        "scenario_count": selected["scenario_count"],
        "path": selected["path"],
    }
    return report


def materialize_gate(gate: str, device: str) -> dict[str, object]:
    contract = load_contract()
    campaigns = _mapping(contract["campaigns"], "campaigns")
    definition = _mapping(campaigns[gate], gate)
    campaign_id = str(_mapping(definition["ids"], f"{gate} IDs")[device])
    rows = _gate_rows(contract, gate, device)
    expected_count = _integer(definition.get("expected_scenario_count"), "scenario count")
    if len(rows) != expected_count:
        raise ProductionReleaseError(
            f"{gate} selected {len(rows)} scenarios; expected {expected_count}"
        )
    catalog = _catalog_path(contract, "core_cpu" if gate == "canary" else device)
    result = plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=TOOL_ROOT / "automated_runs",
        campaign_id=campaign_id,
        scenario_ids=[str(row["scenario_id"]) for row in rows],
        default_max_retries=1,
        created_at=_timestamp(str(definition["created_at_utc"])),
        registry=ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION),
    )
    profile = str(_mapping(_mapping(contract["execution"], "execution")["profiles"], "profiles")[device])
    assignment_path = result.campaign_root / "worker_assignments" / "machine_a_gate.yaml"
    _archive_stale_pending_assignment(
        result.campaign_root,
        assignment_path,
        bound_commit=current_git_commit(REPOSITORY_ROOT),
    )
    assignment = create_worker_assignment(
        result.campaign_root,
        worker_id=str(_mapping(contract["execution"], "execution")["gate_worker_id"]),
        expected_git_commit=current_git_commit(REPOSITORY_ROOT),
        expected_environment_profile=profile,
        scenario_ids=list(result.scenario_ids),
        notes=f"Credential-free production {gate} gate for {device}.",
        created_at=_timestamp(str(definition["created_at_utc"])),
        output_path=assignment_path,
    )
    validate_worker_assignment(
        result.campaign_root,
        assignment_path,
        actual_git_commit=current_git_commit(REPOSITORY_ROOT),
        actual_environment_profile=profile,
    )
    return {
        "schema_version": "production-gate-materialization.v1",
        "gate": gate,
        "device_mode": device,
        "campaign_id": campaign_id,
        "campaign_root": str(result.campaign_root),
        "campaign_manifest_sha256": file_sha256(
            result.campaign_root / "campaign_manifest.json"
        ),
        "scenario_count": len(result.scenario_ids),
        "assignment": str(assignment_path),
        "assignment_id": assignment["assignment_id"],
        "environment_profile": profile,
        "valid": True,
    }


def materialize_rehearsal(device: str) -> dict[str, object]:
    contract = load_contract()
    definition = _mapping(_mapping(contract["campaigns"], "campaigns")["rehearsal"], "rehearsal")
    rows = _rehearsal_rows(contract, device)
    expected = _integer(definition.get("expected_scenario_count"), "scenario count")
    if len(rows) != expected:
        raise ProductionReleaseError(
            f"rehearsal selected {len(rows)} scenarios; expected {expected}"
        )
    campaign_id = str(_mapping(definition["ids"], "rehearsal IDs")[device])
    result = plan_campaign(
        scenario_catalog=_catalog_path(contract, device),
        automated_runs_root=TOOL_ROOT / "automated_runs",
        campaign_id=campaign_id,
        scenario_ids=[str(row["scenario_id"]) for row in rows],
        default_max_retries=1,
        created_at=_timestamp(str(definition["created_at_utc"])),
        registry=ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION),
    )
    profile = str(_mapping(_mapping(contract["execution"], "execution")["profiles"], "profiles")[device])
    assignment_path = result.campaign_root / "worker_assignments" / "machine_a_rehearsal.yaml"
    _archive_stale_pending_assignment(
        result.campaign_root,
        assignment_path,
        bound_commit=current_git_commit(REPOSITORY_ROOT),
    )
    assignment = create_worker_assignment(
        result.campaign_root,
        worker_id=str(_mapping(contract["execution"], "execution")["rehearsal_worker_id"]),
        expected_git_commit=current_git_commit(REPOSITORY_ROOT),
        expected_environment_profile=profile,
        scenario_ids=list(result.scenario_ids),
        notes="Bounded production rehearsal: clean, noise, RIR, RIR+noise, native, speaker source.",
        created_at=_timestamp(str(definition["created_at_utc"])),
        output_path=assignment_path,
    )
    return {
        "schema_version": "production-rehearsal-materialization.v1",
        "device_mode": device,
        "campaign_id": campaign_id,
        "campaign_root": str(result.campaign_root),
        "campaign_manifest_sha256": file_sha256(result.campaign_root / "campaign_manifest.json"),
        "scenario_ids": list(result.scenario_ids),
        "assignment": str(assignment_path),
        "assignment_id": assignment["assignment_id"],
        "environment_profile": profile,
        "valid": True,
    }


def run_gate(gate: str, device: str) -> dict[str, object]:
    if gate == "canary" and device == "cuda":
        return _run_reference_cpu_canary_for_cuda_release()
    contract = load_contract()
    if gate == "small":
        _require_passed_result(
            TOOL_ROOT
            / "artifacts"
            / "production_release"
            / "cpu"
            / "canary_gate_result.json",
            "component canary",
        )
    materialized = materialize_gate(gate, device)
    production_root = TOOL_ROOT / "artifacts" / "production_release" / device
    synthetic_path = _ensure_synthetic(production_root)
    canary_path: Path | None = None
    if gate == "canary":
        canary_path = production_root / "component_canary.json"
        _run_component_canary(canary_path)
    prerequisite = synthetic_path
    if gate == "standard":
        small_id = str(
            _mapping(
                _mapping(_mapping(contract["campaigns"], "campaigns")["small"], "small")["ids"],
                "small IDs",
            )[device]
        )
        prerequisite = (
            TOOL_ROOT
            / "automated_runs"
            / small_id
            / "analysis"
            / "report"
            / "release_qualification.json"
        )
        _require_passed_gate(prerequisite, "small")

    campaign_root = Path(str(materialized["campaign_root"]))
    assignment_path = Path(str(materialized["assignment"]))
    profile = str(materialized["environment_profile"])
    execution = _mapping(contract["execution"], "execution")
    result = run_worker_assignment(
        campaign_root,
        assignment_path,
        project_root=PROJECT_ROOT,
        environment_profile=profile,
        minimum_free_disk_bytes=int(
            _number(execution.get("minimum_free_disk_gb"), "minimum free disk") * 1024**3
        ),
        telemetry_enabled=bool(execution["telemetry_enabled"]),
        telemetry_interval_sec=_number(
            execution.get("telemetry_interval_sec"), "telemetry interval"
        ),
    )
    _require_successful_campaign(campaign_root)

    transfer_root = production_root / "transfers" / str(materialized["campaign_id"])
    if transfer_root.exists():
        validate_worker_transfer(transfer_root, campaign_root=campaign_root)
    else:
        export_worker_results(
            campaign_root,
            assignment_path,
            transfer_root,
            repository_root=REPOSITORY_ROOT,
            actual_git_commit=current_git_commit(REPOSITORY_ROOT),
            actual_environment_profile=profile,
        )
    validate_worker_transfer(transfer_root, campaign_root=campaign_root)
    merge_worker_results(campaign_root, [transfer_root])
    validate_merged_results(campaign_root)
    analysis = analyze_campaign(
        campaign_root,
        prerequisite_evidence_path=prerequisite,
    )
    release_path = campaign_root / "analysis" / "report" / "release_qualification.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if gate in {"small", "standard"} and release.get("passed") is not True:
        raise ProductionReleaseError(
            f"{gate} release qualification is blocked; inspect {release_path}"
        )
    report = {
        "schema_version": "production-gate-result.v1",
        "gate": gate,
        "device_mode": device,
        "materialization": materialized,
        "executor": result.to_jsonable(),
        "component_canary": str(canary_path) if canary_path else None,
        "transfer_root": str(transfer_root),
        "analysis": analysis,
        "release_qualification": str(release_path),
        "passed": release.get("passed") is True,
    }
    atomic_write_json(production_root / f"{gate}_gate_result.json", report)
    return report


def _run_reference_cpu_canary_for_cuda_release() -> dict[str, object]:
    """Run the CPU-identity core canary before CUDA scientific campaigns."""

    cpu_python = REPOSITORY_ROOT / ".venv" / "Scripts" / "python.exe"
    if not cpu_python.is_file():
        raise ProductionReleaseError(
            "the CUDA release chain requires the supported CPU reference environment"
        )
    command = [
        str(cpu_python),
        str(Path(__file__).resolve()),
        "run-gate",
        "--device",
        "cpu",
        "--gate",
        "canary",
    ]
    completed = subprocess.run(command, cwd=TOOL_ROOT, check=False)
    if completed.returncode != 0:
        raise ProductionReleaseError("CPU reference canary failed")
    report_path = (
        TOOL_ROOT
        / "artifacts"
        / "production_release"
        / "cpu"
        / "canary_gate_result.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["requested_release_device"] = "cuda"
    report["execution_note"] = (
        "Core component canary uses its canonical CPU scenarios and core-cpu "
        "environment; subsequent release gates use explicit CUDA scenarios."
    )
    return report


def run_rehearsal(
    device: str,
    *,
    resume_stopped: bool,
    max_scenarios: int | None = None,
) -> dict[str, object]:
    """Execute the six-case rehearsal without expanding or mutating scenarios."""

    materialized = materialize_rehearsal(device)
    contract = load_contract()
    execution = _mapping(contract["execution"], "execution")
    result = run_worker_assignment(
        Path(str(materialized["campaign_root"])),
        Path(str(materialized["assignment"])),
        project_root=PROJECT_ROOT,
        environment_profile=str(materialized["environment_profile"]),
        max_scenarios=max_scenarios,
        minimum_free_disk_bytes=int(
            _number(execution.get("minimum_free_disk_gb"), "minimum free disk") * 1024**3
        ),
        telemetry_enabled=bool(execution["telemetry_enabled"]),
        telemetry_interval_sec=_number(
            execution.get("telemetry_interval_sec"), "telemetry interval"
        ),
        resume_stopped=resume_stopped,
    )
    return {
        "schema_version": "production-rehearsal-execution.v1",
        "device_mode": device,
        "materialization": materialized,
        "executor": result.to_jsonable(),
    }


def finalize_rehearsal(device: str) -> dict[str, object]:
    """Prove export, transfer validation, merge, and analysis on the rehearsal."""

    materialized = materialize_rehearsal(device)
    campaign_root = Path(str(materialized["campaign_root"]))
    assignment_path = Path(str(materialized["assignment"]))
    profile = str(materialized["environment_profile"])
    _require_successful_campaign(campaign_root)
    production_root = TOOL_ROOT / "artifacts" / "production_release" / device
    transfer_root = production_root / "transfers" / str(materialized["campaign_id"])
    if transfer_root.exists():
        validate_worker_transfer(transfer_root, campaign_root=campaign_root)
    else:
        export_worker_results(
            campaign_root,
            assignment_path,
            transfer_root,
            repository_root=REPOSITORY_ROOT,
            actual_git_commit=current_git_commit(REPOSITORY_ROOT),
            actual_environment_profile=profile,
        )
    transfer = validate_worker_transfer(transfer_root, campaign_root=campaign_root)
    merge = merge_worker_results(campaign_root, [transfer_root])
    merged = validate_merged_results(campaign_root)
    prerequisite = _ensure_synthetic(production_root)
    analysis = analyze_campaign(
        campaign_root,
        prerequisite_evidence_path=prerequisite,
    )
    expected = _integer(
        _mapping(
            _mapping(load_contract()["campaigns"], "campaigns")["rehearsal"],
            "rehearsal",
        ).get("expected_scenario_count"),
        "rehearsal scenario count",
    )
    passed = (
        int(analysis["planned_scenario_count"]) == expected
        and int(analysis["included_scenario_count"]) == expected
        and int(analysis["coverage_blocker_count"]) == 0
    )
    if not passed:
        raise ProductionReleaseError(
            f"rehearsal analysis did not reconcile {expected} scenarios: {analysis}"
        )
    report = {
        "schema_version": "production-rehearsal-finalization.v1",
        "device_mode": device,
        "campaign_id": materialized["campaign_id"],
        "scenario_count": expected,
        "transfer_root": str(transfer_root),
        "transfer_validation": transfer,
        "merge": merge,
        "merged_validation": merged,
        "analysis": analysis,
        "release_gate_note": (
            "The deliberately mixed-tier rehearsal validates operations; it is not "
            "a small, standard, or large scientific release gate."
        ),
        "passed": True,
    }
    atomic_write_json(production_root / "rehearsal_result.json", report)
    return report


def run_gates(device: str, through: str) -> dict[str, object]:
    order = ["canary", "small", "standard"]
    limit = "standard" if through == "all" else through
    selected = order[: order.index(limit) + 1]
    results = []
    for gate in selected:
        result = run_gate(gate, device)
        if result.get("passed") is not True:
            raise ProductionReleaseError(f"{gate} gate did not pass")
        results.append(result)
    return {
        "schema_version": "production-release-gates.v1",
        "device_mode": device,
        "gates": results,
        "passed": all(result["passed"] for result in results),
    }


def _gate_rows(
    contract: Mapping[str, object], gate: str, device: str
) -> list[dict[str, object]]:
    campaigns = _mapping(contract["campaigns"], "campaigns")
    definition = _mapping(campaigns[gate], gate)
    if gate != "canary":
        tier = str(definition["tier"])
        return sorted(
            [row for row in read_jsonl(_catalog_path(contract, device)) if row.get("tier") == tier],
            key=lambda row: str(row["scenario_id"]),
        )
    rows = list(read_jsonl(_catalog_path(contract, "core_cpu")))
    candidates = [
        row
        for row in rows
        if row.get("tier") == "small"
        and row.get("panel") == "controlled_clean"
        and _mapping(row.get("dataset_slice"), "dataset slice").get("dataset") == "cmu_arctic"
        and _mapping(row.get("condition"), "condition").get("id") == "clean"
        and _mapping(row.get("pipeline"), "pipeline").get("environment_profile") == "core-cpu"
    ]
    selected: list[dict[str, object]] = []
    for signature in _items(
        definition.get("component_signatures"), "component signatures"
    ):
        expected = {str(key): str(value) for key, value in _mapping(signature, "component signature").items()}
        matches = [row for row in candidates if _enabled_components(row) == expected]
        if len(matches) != 1:
            raise ProductionReleaseError(
                f"canary signature {expected} matched {len(matches)} scenarios"
            )
        selected.append(matches[0])
    return sorted(selected, key=lambda row: str(row["scenario_id"]))


def _rehearsal_rows(
    contract: Mapping[str, object], device: str
) -> list[dict[str, object]]:
    definition = _mapping(_mapping(contract["campaigns"], "campaigns")["rehearsal"], "rehearsal")
    rows = list(read_jsonl(_catalog_path(contract, device)))
    selected: list[dict[str, object]] = []
    for raw_selector in _items(definition.get("selectors"), "rehearsal selectors"):
        selector = _mapping(raw_selector, "rehearsal selector")
        matches = [row for row in rows if _matches_selector(row, selector)]
        if not matches:
            raise ProductionReleaseError(f"rehearsal selector matched no scenario: {selector}")
        selected.append(sorted(matches, key=lambda row: str(row["scenario_id"]))[0])
    if len({str(row["scenario_id"]) for row in selected}) != len(selected):
        raise ProductionReleaseError("rehearsal selectors produced duplicate scenarios")
    return sorted(selected, key=lambda row: str(row["scenario_id"]))


def _matches_selector(row: Mapping[str, object], selector: Mapping[str, object]) -> bool:
    data_slice = _mapping(row.get("dataset_slice"), "dataset slice")
    condition = _mapping(row.get("condition"), "condition")
    filters = _mapping(data_slice.get("filters"), "dataset filters")
    values = {
        "panel": row.get("panel"),
        "tier": row.get("tier"),
        "dataset": data_slice.get("dataset"),
        "condition": condition.get("id"),
        "role": filters.get("role"),
    }
    return all(values.get(str(key)) == value for key, value in selector.items())


def _enabled_components(row: Mapping[str, object]) -> dict[str, str]:
    pipeline = _mapping(row.get("pipeline"), "pipeline")
    components = _mapping(pipeline.get("components"), "components")
    return {
        str(family): str(_mapping(component, str(family)).get("name"))
        for family, component in components.items()
        if bool(_mapping(component, str(family)).get("enabled"))
    }


def _catalog_path(contract: Mapping[str, object], key: str) -> Path:
    relative = str(_mapping(contract["catalogs"], "catalogs")[key])
    path = (TOOL_ROOT / relative).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _ensure_synthetic(production_root: Path) -> Path:
    output = production_root / "synthetic"
    path = output / "synthetic_release_qualification.json"
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("passed") is True and existing.get("target_gate") == "synthetic":
            return path
    qualify_synthetic_release(TOOL_ROOT, output)
    return path


def _run_component_canary(output: Path) -> None:
    if output.is_file():
        value = json.loads(output.read_text(encoding="utf-8"))
        if _mapping(value.get("summary"), "canary summary").get(
            "all_available_core_qualified"
        ) is True:
            return
    command = [
        sys.executable,
        str(TOOL_ROOT / "run_evaluation.py"),
        "screening",
        "qualify",
        "--project-root",
        str(PROJECT_ROOT),
        "--repetitions",
        "2",
        "--reference-asr",
        "whisper_base",
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, cwd=TOOL_ROOT, check=False)
    if completed.returncode != 0:
        raise ProductionReleaseError("production component canary failed")


def _validate_required_assets(contract: Mapping[str, object]) -> None:
    scope = _mapping(contract["production_scope"], "production scope")
    failures = []
    for raw in _items(scope.get("required_models"), "required models"):
        asset = _mapping(raw, "required model")
        path = REPOSITORY_ROOT / str(asset["path"])
        expected = str(asset["sha256"]).upper()
        if not path.is_file():
            failures.append(f"missing {asset['id']}: {path}")
        elif file_sha256(path) != expected:
            failures.append(f"hash mismatch {asset['id']}: {path}")
    if failures:
        raise ProductionReleaseError("; ".join(failures))


def _require_successful_campaign(campaign_root: Path) -> None:
    validate_campaign(campaign_root)
    manifest = json.loads((campaign_root / "campaign_manifest.json").read_text(encoding="utf-8"))
    summary = CampaignStateStore(campaign_root / "database" / "campaign.sqlite").summary(
        str(manifest["campaign_id"])
    )
    incomplete = {
        key: value
        for key, value in summary["state_counts"].items()
        if key not in {"succeeded", "succeeded_with_warnings"}
    }
    if incomplete:
        raise ProductionReleaseError(f"campaign is incomplete: {incomplete}")


def _require_passed_gate(path: Path, gate: str) -> None:
    if not path.is_file():
        raise ProductionReleaseError(f"{gate} prerequisite is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("target_gate") != gate or value.get("passed") is not True:
        raise ProductionReleaseError(f"{gate} prerequisite did not pass: {path}")


def _require_passed_result(path: Path, label: str) -> None:
    if not path.is_file():
        raise ProductionReleaseError(f"{label} result is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("passed") is not True:
        raise ProductionReleaseError(f"{label} did not pass: {path}")


def _archive_stale_pending_assignment(
    campaign_root: Path,
    assignment_path: Path,
    *,
    bound_commit: str,
) -> None:
    """Archive an obsolete assignment only while the campaign is untouched."""

    if not assignment_path.is_file():
        return
    existing = yaml.safe_load(assignment_path.read_text(encoding="utf-8"))
    if not isinstance(existing, Mapping):
        raise ProductionReleaseError(f"invalid existing assignment: {assignment_path}")
    if str(existing.get("expected_git_commit") or "") == bound_commit:
        return
    manifest = json.loads(
        (campaign_root / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    state = CampaignStateStore(campaign_root / "database" / "campaign.sqlite")
    summary = state.summary(str(manifest["campaign_id"]))
    expected = len(manifest["scenario_ids"])
    if summary["state_counts"] != {"pending": expected}:
        raise ProductionReleaseError(
            "refusing to rebind a release-gate assignment after campaign work started"
        )
    history = campaign_root / "worker_assignments" / "history"
    history.mkdir(parents=True, exist_ok=True)
    assignment_id = str(existing.get("assignment_id") or "unknown")
    destination = history / f"{assignment_path.stem}_{assignment_id}.yaml"
    if destination.exists():
        if destination.read_bytes() != assignment_path.read_bytes():
            raise ProductionReleaseError(
                f"release-gate assignment history conflicts: {destination}"
            )
        assignment_path.unlink()
    else:
        assignment_path.replace(destination)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ProductionReleaseError(f"{label} must be an object")
    return value


def _items(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ProductionReleaseError(f"{label} must be a list")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ProductionReleaseError(f"{label} must be an integer")
    return int(value)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ProductionReleaseError(f"{label} must be numeric")
    return float(value)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.action == "materialize":
            report = materialize_launch(
                args.device,
                args.machine_id,
                bind_current_commit=args.bind_current_commit,
            )
        elif args.action == "run-gates":
            report = run_gates(args.device, args.through)
        elif args.action == "run-gate":
            report = run_gate(args.gate, args.device)
        elif args.action == "run-rehearsal":
            report = run_rehearsal(
                args.device,
                resume_stopped=args.resume_stopped,
                max_scenarios=args.max_scenarios,
            )
        elif args.action == "finalize-rehearsal":
            report = finalize_rehearsal(args.device)
        else:
            report = materialize_rehearsal(args.device)
    except (RuntimeError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"production release error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
