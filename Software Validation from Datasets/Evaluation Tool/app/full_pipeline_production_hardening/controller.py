"""Restart-safe actions for bounded Prompt-7 selection and hardening."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_file,
)

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_ROOT,
    PROMPT5_MARKER,
    PROMPT5_REQUIRED_FILES,
    PROMPT6_MARKER,
    PROMPT6_REQUIRED_FILES,
    TOOL_ROOT,
    scope_fields,
)
from .gate import validate_prerequisites as prerequisite_gate
from .io import (
    HardeningError,
    ensure_c,
    storage_guard,
    write_csv,
    write_json_once,
)
from .plan import build_acceptance_plan
from .selection import h2_simplicity_rows, select_candidates
from .universal import single_artifact, validate_completion


@dataclass(frozen=True)
class Layout:
    root: Path
    authorization: Path
    selection: Path
    plan: Path
    execution: Path
    evidence_index: Path
    packaging: Path
    report: Path
    completion: Path
    progress: Path
    controller_log: Path


def layout(root: Path | str = DEFAULT_ROOT) -> Layout:
    base = ensure_c(root, label="Prompt-7 workspace")
    try:
        base.relative_to(TOOL_ROOT.resolve())
    except ValueError as exc:
        raise HardeningError(
            f"Prompt-7 output workspace must remain beneath the Evaluation Tool root: {base}"
        ) from exc
    return Layout(
        root=base,
        authorization=base / "prompt7_authorization.json",
        selection=base / "selection/selection.json",
        plan=base / "acceptance_plan.json",
        execution=base / "acceptance_execution.json",
        evidence_index=base / "report/evidence_index.json",
        packaging=base / "packaging.json",
        report=base / "report",
        completion=base / "completion_marker.json",
        progress=base / "program_progress.json",
        controller_log=base / "controller.log",
    )


def validate_prerequisites(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths = layout(workspace_root)
    paths.root.mkdir(parents=True, exist_ok=True)
    storage = storage_guard(paths.root)
    authorization = prerequisite_gate(
        prompt6_marker=prompt6_marker,
        prompt5_marker=prompt5_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    write_json_once(paths.authorization, authorization)
    return {
        "schema_version": "full-pipeline-production-hardening-prerequisite-result.v1",
        **scope_fields(),
        "status": "PASS",
        "authorization": authorization,
        "storage_guard": storage,
        "outcomes_opened": False,
        "inference_started": False,
    }


def select(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, authorization = _require_authorization(
        workspace_root,
        prompt6_marker=prompt6_marker,
        prompt5_marker=prompt5_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    storage_guard(paths.root)
    evidence = _evidence_files(authorization)
    candidate_ids = authorization.get("predeclared_extended_pipeline_ids")
    if not isinstance(candidate_ids, list):
        raise HardeningError("authorization candidate pool is absent")
    from .io import read_csv

    extended_rows = read_csv(evidence["extended_summary.csv"])
    extended_ids = {
        str(row.get("pipeline_id") or row.get("preset_id") or "")
        for row in extended_rows
    }
    missing_extended = sorted(set(str(item) for item in candidate_ids) - extended_ids)
    if missing_extended:
        raise HardeningError(
            "Prompt-6 extended summary lacks predeclared candidates: "
            + ", ".join(missing_extended)
        )
    runtime_bindings = authorization.get("runtime_candidate_bindings")
    if not isinstance(runtime_bindings, Mapping):
        raise HardeningError("authorization runtime candidate bindings are absent")
    value = select_candidates(
        candidate_ids=candidate_ids,
        evidence_files=evidence,
        runtime_bindings={
            str(key): dict(row)
            for key, row in runtime_bindings.items()
            if isinstance(row, Mapping)
        },
    )
    value["authorization_sha256"] = sha256_file(paths.authorization)
    value["evidence_files"] = {
        name: {"path": str(path), "sha256": sha256_file(path)}
        for name, path in sorted(evidence.items())
    }
    write_json_once(paths.selection, value)
    write_csv(
        paths.report / "h2_simplicity_measurement.csv",
        h2_simplicity_rows(value),
    )
    return value


def prepare_hardening(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, authorization = _require_authorization(
        workspace_root,
        prompt6_marker=prompt6_marker,
        prompt5_marker=prompt5_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    storage_guard(paths.root)
    selection = _require_json(paths.selection, "Select")
    _validate_selection_binding(selection, paths)
    inputs = authorization.get("hardening_inputs")
    if not isinstance(inputs, Mapping):
        raise HardeningError("authorization hardening inputs are absent")
    value = build_acceptance_plan(
        workspace_root=paths.root,
        selection=selection,
        hardening_inputs=inputs,
    )
    value["selection_sha256"] = sha256_file(paths.selection)
    value["authorization_sha256"] = sha256_file(paths.authorization)
    write_json_once(paths.plan, value)
    return value


def run_hardening(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, _ = _require_authorization(
        workspace_root,
        prompt6_marker=prompt6_marker,
        prompt5_marker=prompt5_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    plan = _require_json(paths.plan, "PrepareHardening")
    _validate_plan_binding(plan, paths)
    storage_guard(paths.root)
    from .runner import run_plan

    return run_plan(workspace_root=paths.root, plan=plan)


def validate_hardening(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, _ = _require_authorization(
        workspace_root,
        prompt6_marker=prompt6_marker,
        prompt5_marker=prompt5_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    plan = _require_json(paths.plan, "PrepareHardening")
    _validate_plan_binding(plan, paths)
    from .validation import validate_acceptance

    return validate_acceptance(workspace_root=paths.root, plan=plan)


def package(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None = None,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, authorization = _require_authorization(
        workspace_root,
        prompt6_marker=prompt6_marker,
        prompt5_marker=prompt5_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    selection = _require_json(paths.selection, "Select")
    evidence = _require_json(paths.evidence_index, "ValidateHardening")
    if evidence.get("status") != "PASS":
        raise HardeningError("BLOCKED_PRODUCTION_CANDIDATE: acceptance did not pass")
    storage_guard(paths.root)
    from .packaging import package_candidates

    return package_candidates(
        workspace_root=paths.root,
        authorization=authorization,
        selection=selection,
        evidence_index=evidence,
    )


def status(*, workspace_root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    plan = read_json(paths.plan) if paths.plan.is_file() else {}
    tasks = plan.get("tasks") if isinstance(plan, Mapping) else None
    raw_tasks = tasks if isinstance(tasks, list) else []
    passed = failed = terminal = 0
    for raw in raw_tasks:
        if not isinstance(raw, Mapping):
            continue
        latest = paths.root / "evidence" / str(raw.get("task_id")) / "latest.json"
        if not latest.is_file():
            continue
        value = read_json(latest)
        terminal += 1
        passed += int(value.get("status") == "PASS")
        failed += int(value.get("status") not in {"PASS", "STOPPED"})
    return {
        "schema_version": "full-pipeline-production-hardening-status.v1",
        **scope_fields(),
        "status": (
            "COMPLETE"
            if paths.completion.is_file()
            else "RUNNING_OR_RESTARTABLE"
            if terminal
            else "NOT_STARTED_OR_PREPARED"
        ),
        "planned_task_count": len(raw_tasks),
        "terminal_task_count": terminal,
        "passed_task_count": passed,
        "failed_task_count": failed,
        "completion_record_exists": paths.completion.is_file(),
        "workspace_root": str(paths.root),
    }


def stop(*, workspace_root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    from .runner import request_stop

    return request_stop(layout(workspace_root).root)


def _require_authorization(
    workspace_root: Path | str,
    *,
    prompt6_marker: Path | str,
    prompt5_marker: Path | str | None,
    amendment_path: Path | str,
    program_state_path: Path | str,
    pi_deployment_steering_path: Path | str,
) -> tuple[Layout, dict[str, object]]:
    paths = layout(workspace_root)
    if not paths.authorization.is_file():
        raise HardeningError("ValidatePrerequisites must run first")
    expected = prerequisite_gate(
        prompt6_marker=prompt6_marker,
        prompt5_marker=prompt5_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    existing = read_json(paths.authorization)
    if canonical_json_bytes(existing) != canonical_json_bytes(expected):
        raise HardeningError("immutable Prompt-7 authorization differs")
    return paths, existing


def _evidence_files(authorization: Mapping[str, object]) -> dict[str, Path]:
    p5_ref = authorization.get("prompt5_completion")
    p6_ref = authorization.get("prompt6_completion")
    if not isinstance(p5_ref, Mapping) or not isinstance(p6_ref, Mapping):
        raise HardeningError("authorization completion references are absent")
    p5 = validate_completion(
        str(p5_ref["path"]),
        prompt_index=5,
        marker=PROMPT5_MARKER,
        required_basenames=PROMPT5_REQUIRED_FILES,
    )
    p6 = validate_completion(
        str(p6_ref["path"]),
        prompt_index=6,
        marker=PROMPT6_MARKER,
        required_basenames=PROMPT6_REQUIRED_FILES,
    )
    result: dict[str, Path] = {}
    for evidence, names in ((p5, PROMPT5_REQUIRED_FILES), (p6, PROMPT6_REQUIRED_FILES)):
        for name in names:
            if name.casefold().endswith(".csv"):
                result[name] = single_artifact(evidence, name)
    return result


def _require_json(path: Path, action: str) -> dict[str, object]:
    if not path.is_file():
        raise HardeningError(f"{action} must complete first: {path}")
    return read_json(path)


def _validate_selection_binding(value: Mapping[str, object], paths: Layout) -> None:
    if value.get("authorization_sha256") != sha256_file(paths.authorization):
        raise HardeningError("selection authorization binding differs")
    if value.get("production_threshold_retuning_performed") is not False:
        raise HardeningError("selection indicates threshold retuning")


def _validate_plan_binding(value: Mapping[str, object], paths: Layout) -> None:
    if value.get("selection_sha256") != sha256_file(paths.selection):
        raise HardeningError("acceptance plan selection binding differs")
    if value.get("authorization_sha256") != sha256_file(paths.authorization):
        raise HardeningError("acceptance plan authorization binding differs")
    if value.get("threshold_changes_allowed") is not False:
        raise HardeningError("acceptance plan permits threshold changes")


__all__ = [
    "Layout",
    "layout",
    "package",
    "prepare_hardening",
    "run_hardening",
    "select",
    "status",
    "stop",
    "validate_hardening",
    "validate_prerequisites",
]
