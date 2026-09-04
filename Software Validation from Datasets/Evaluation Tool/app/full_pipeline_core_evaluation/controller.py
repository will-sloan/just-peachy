"""Restart-safe Prompt-5 reduced held-out orchestration actions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline_evaluation import controller as evaluation_controller
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_evaluation.store import EvaluationStateStore
from app.utils.paths import resolve_data_path_from_logical

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_CASE_MANIFEST,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_ROOT,
    EXPECTED_SELECTED_CASE_SHA256,
    SELECTION_SEED,
    TOOL_ROOT,
)
from .gate import validate_authorization, validate_prompt4_freeze
from .io import (
    CoreEvaluationError,
    ensure_c_drive,
    read_jsonl,
    scope_fields,
    storage_preflight,
    write_json_once,
    write_jsonl_once,
)
from .selection import (
    case_id,
    select_reduced_panel,
    selected_case_sha256,
    selection_manifest,
    validate_selected_panel,
)


EXPECTED_INPUT_CASE_MANIFEST_SHA256 = (
    "0928e71c408ba3ad8e86dc7d30ab3f3765f53af3af7fdecf7781d8ce47d2c4d1"
)
ACCURACY_STAGE = "prompt5_reduced_core_accuracy_8day_v1"
RESOURCE_STAGE = "prompt5_reduced_core_serial_resources_8day_v1"
AUTHORIZATION_FILE = "prompt5_authorization.json"
SELECTION_MANIFEST_FILE = "selection/selection_manifest.json"


@dataclass(frozen=True)
class Layout:
    root: Path
    selection: Path
    selected_cases: Path
    excluded_cases: Path
    authorization: Path
    accuracy: Path
    resources: Path
    results: Path
    report: Path
    completion_marker: Path


def layout(root: Path | str = DEFAULT_ROOT) -> Layout:
    base = ensure_c_drive(root, label="Prompt-5 workspace")
    return Layout(
        root=base,
        selection=base / "selection",
        selected_cases=base / "selection/selected_cases.jsonl",
        excluded_cases=base / "selection/excluded_cases.jsonl",
        authorization=base / AUTHORIZATION_FILE,
        accuracy=base / "accuracy",
        resources=base / "resources",
        results=base / "results",
        report=base / "report",
        completion_marker=base / "completion_marker.json",
    )


def validate_freeze(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt4_marker: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths = layout(workspace_root)
    storage = storage_preflight(paths.root)
    authorization = validate_prompt4_freeze(
        prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    if paths.authorization.is_file():
        existing = read_json(paths.authorization)
        if canonical_json_bytes(existing) != canonical_json_bytes(authorization):
            raise CoreEvaluationError("immutable Prompt-5 authorization differs")
    else:
        write_json_once(paths.authorization, authorization)
    return {
        "schema_version": "full-pipeline-core-validate-freeze-result.v1",
        **scope_fields(),
        "status": "PASS",
        "authorization": authorization,
        "storage_preflight": storage,
        "held_out_predictions_inspected": False,
        "inference_started": False,
    }


def prepare_reduced(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt4_marker: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    case_manifest_path: Path | str = DEFAULT_CASE_MANIFEST,
) -> dict[str, object]:
    """Freeze metadata/reference selection; do not run or open predictions."""

    paths = layout(workspace_root)
    gate = _require_authorization(
        paths,
        prompt4_marker=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    storage = storage_preflight(paths.root)
    source_manifest = ensure_c_drive(
        case_manifest_path, label="held-out case manifest", must_exist=True
    )
    input_sha = sha256_file(source_manifest)
    if input_sha != EXPECTED_INPUT_CASE_MANIFEST_SHA256:
        raise CoreEvaluationError(
            "prepared held-out case-manifest identity differs: " + input_sha
        )
    all_cases = read_jsonl(source_manifest)
    selected, excluded = select_reduced_panel(all_cases, seed=SELECTION_SEED)
    _validate_material_paths(selected)
    reference_paths = _reference_paths()
    reference_hashes = {
        str(path.relative_to(TOOL_ROOT).as_posix()): sha256_file(path)
        for path in reference_paths
    }
    manifest = selection_manifest(
        selected,
        excluded,
        input_manifest_path=source_manifest,
        reference_hashes=reference_hashes,
    )
    manifest["authorization_identity_sha256"] = gate["authorization_identity_sha256"]
    manifest["core_orchestration_source_sha256"] = _source_identity()
    manifest["selected_cases_path"] = str(paths.selected_cases)
    manifest["excluded_cases_path"] = str(paths.excluded_cases)
    paths.selection.mkdir(parents=True, exist_ok=True)
    write_jsonl_once(paths.selected_cases, selected)
    write_jsonl_once(paths.excluded_cases, excluded)
    write_json_once(paths.root / SELECTION_MANIFEST_FILE, manifest)

    registry_path = Path(
        str(gate["decision_policy_registry"]["path"])  # type: ignore[index]
    )
    prepared = evaluation_controller.prepare(
        workspace_root=paths.accuracy,
        seed=SELECTION_SEED,
        case_ids=tuple(case_id(row) for row in selected),
        pipeline_ids=matrix().pipeline_ids,
        measurement_modes=("accuracy",),
        campaign_stage=ACCURACY_STAGE,
        decision_policy_registry_path=registry_path,
    )
    _bind_local_result_paths(paths, paths.accuracy, "accuracy")
    campaign = _validate_stage_manifest(
        paths.accuracy,
        stage=ACCURACY_STAGE,
        selected=selected,
        measurement_mode="accuracy",
        expected_job_count=126,
        registry_path=registry_path,
    )
    preparation = {
        "schema_version": "full-pipeline-core-reduced-preparation.v1",
        **scope_fields(),
        "status": "PREPARED_NOT_RUN",
        "selection_manifest_sha256": sha256_file(paths.root / SELECTION_MANIFEST_FILE),
        "selected_case_count": len(selected),
        "selected_case_sha256": selected_case_sha256(selected),
        "accuracy_campaign_id": campaign["campaign_id"],
        "accuracy_job_count": campaign["job_count"],
        "pipeline_count": 18,
        "storage_preflight": storage,
        "controller_preparation": prepared,
        "held_out_predictions_inspected": False,
        "inference_started": False,
    }
    write_json_once(paths.root / "preparation.json", preparation)
    return preparation


def run_accuracy(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt4_marker: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    parallel_jobs: int = 2,
) -> dict[str, object]:
    if parallel_jobs not in {1, 2}:
        raise CoreEvaluationError("accuracy parallel_jobs must be 1 or 2")
    paths, selected, registry = _require_prepared(
        workspace_root,
        prompt4_marker=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    storage_preflight(paths.root)
    _validate_stage_manifest(
        paths.accuracy,
        stage=ACCURACY_STAGE,
        selected=selected,
        measurement_mode="accuracy",
        expected_job_count=126,
        registry_path=registry,
    )
    # The generic public RunEvaluation gate is same-workspace by design. Prompt 5
    # instead validates the external all-18 Prompt-4 freeze above, then delegates
    # only the already-tested queue runner.
    result = evaluation_controller._run(  # noqa: SLF001
        workspace_root=paths.accuracy,
        split="evaluation",
        measurement_mode="accuracy",
        pipeline_ids=matrix().pipeline_ids,
        protocol_ids=(),
        parallel_jobs=parallel_jobs,
        job_executor=None,
    )
    return {
        "schema_version": "full-pipeline-core-run-accuracy.v1",
        **scope_fields(),
        "status": "RUN_FINISHED",
        "parallel_jobs": parallel_jobs,
        "controller_result": result,
    }


def validate_accuracy(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt4_marker: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, selected, registry = _require_prepared(
        workspace_root,
        prompt4_marker=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    manifest = _validate_stage_manifest(
        paths.accuracy,
        stage=ACCURACY_STAGE,
        selected=selected,
        measurement_mode="accuracy",
        expected_job_count=126,
        registry_path=registry,
    )
    result = _validate_terminal_jobs(paths.accuracy, expected_job_count=126)
    value = {
        "schema_version": "full-pipeline-core-accuracy-validation.v1",
        **scope_fields(),
        "status": (
            "PASS_WITH_EXPLICIT_FAILURES"
            if result["explicit_failure_count"]
            else "PASS"
        ),
        "campaign_id": manifest["campaign_id"],
        **result,
    }
    write_json_atomic(paths.root / "accuracy_validation.json", value)
    return value


def prepare_resources(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt4_marker: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, selected, registry = _require_prepared(
        workspace_root,
        prompt4_marker=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    validation = validate_accuracy(
        workspace_root=paths.root,
        prompt4_marker=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    storage_preflight(paths.root)
    resource_case = _resource_case(selected)
    prepared = evaluation_controller.prepare(
        workspace_root=paths.resources,
        seed=SELECTION_SEED,
        case_ids=(case_id(resource_case),),
        pipeline_ids=matrix().pipeline_ids,
        measurement_modes=("resources",),
        campaign_stage=RESOURCE_STAGE,
        decision_policy_registry_path=registry,
    )
    _bind_local_result_paths(paths, paths.resources, "resources")
    manifest = _validate_stage_manifest(
        paths.resources,
        stage=RESOURCE_STAGE,
        selected=(resource_case,),
        measurement_mode="resources",
        expected_job_count=18,
        registry_path=registry,
    )
    value = {
        "schema_version": "full-pipeline-core-resource-preparation.v1",
        **scope_fields(),
        "status": "PREPARED_NOT_RUN",
        "resource_case_id": case_id(resource_case),
        "resource_selection_rule": (
            "minimum sha256(prompt5_resource_serial_v1|5107|protocol_case_id) "
            "among selected primary gallery-size-10 mixed-known-unknown Product V2 cases"
        ),
        "resource_job_count": manifest["job_count"],
        "accuracy_validation_status": validation["status"],
        "controller_preparation": prepared,
    }
    write_json_once(paths.root / "resource_preparation.json", value)
    return value


def run_resources(
    *,
    workspace_root: Path | str = DEFAULT_ROOT,
    prompt4_marker: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    paths, selected, registry = _require_prepared(
        workspace_root,
        prompt4_marker=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    if not (paths.root / "resource_preparation.json").is_file():
        raise CoreEvaluationError("PrepareResources must complete before RunResources")
    storage_preflight(paths.root)
    resource_case = _resource_case(selected)
    _validate_stage_manifest(
        paths.resources,
        stage=RESOURCE_STAGE,
        selected=(resource_case,),
        measurement_mode="resources",
        expected_job_count=18,
        registry_path=registry,
    )
    result = evaluation_controller._run(  # noqa: SLF001
        workspace_root=paths.resources,
        split="evaluation",
        measurement_mode="resources",
        pipeline_ids=matrix().pipeline_ids,
        protocol_ids=(),
        parallel_jobs=1,
        job_executor=None,
    )
    return {
        "schema_version": "full-pipeline-core-run-resources.v1",
        **scope_fields(),
        "status": "RUN_FINISHED",
        "parallel_jobs": 1,
        "serial_resource_comparison": True,
        "controller_result": result,
    }


def validate_resources(workspace_root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    result = _validate_terminal_jobs(paths.resources, expected_job_count=18)
    value = {
        "schema_version": "full-pipeline-core-resource-validation.v1",
        **scope_fields(),
        "status": (
            "PASS_WITH_EXPLICIT_FAILURES"
            if result["explicit_failure_count"]
            else "PASS"
        ),
        "serial_resource_comparison": True,
        **result,
    }
    write_json_atomic(paths.root / "resource_validation.json", value)
    return value


def status(*, workspace_root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    stages: dict[str, object] = {}
    for name, root in (("accuracy", paths.accuracy), ("resources", paths.resources)):
        if (root / "campaign_manifest.json").is_file():
            stages[name] = evaluation_controller.status(workspace_root=root)
        else:
            stages[name] = {"status": "NOT_PREPARED"}
    return {
        "schema_version": "full-pipeline-core-status.v1",
        **scope_fields(),
        "status": "AVAILABLE",
        "stages": stages,
        "completion_marker_exists": paths.completion_marker.is_file(),
    }


def stop(*, workspace_root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    paths = layout(workspace_root)
    stopped: dict[str, object] = {}
    for name, root in (("accuracy", paths.accuracy), ("resources", paths.resources)):
        if (root / "campaign_manifest.json").is_file():
            stopped[name] = evaluation_controller.stop(workspace_root=root)
    return {
        "schema_version": "full-pipeline-core-stop.v1",
        **scope_fields(),
        "status": "STOP_REQUESTED",
        "stages": stopped,
    }


def _require_authorization(
    paths: Layout,
    *,
    prompt4_marker: Path | str,
    amendment_path: Path | str,
    program_state_path: Path | str,
    pi_deployment_steering_path: Path | str,
) -> dict[str, object]:
    if not paths.authorization.is_file():
        raise CoreEvaluationError("ValidateFreeze must complete before this action")
    value = read_json(paths.authorization)
    return validate_authorization(
        value,
        marker_path=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )


def _require_prepared(
    workspace_root: Path | str,
    *,
    prompt4_marker: Path | str,
    amendment_path: Path | str,
    program_state_path: Path | str,
    pi_deployment_steering_path: Path | str,
) -> tuple[Layout, list[dict[str, object]], Path]:
    paths = layout(workspace_root)
    gate = _require_authorization(
        paths,
        prompt4_marker=prompt4_marker,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    if (
        not paths.selected_cases.is_file()
        or not (paths.root / SELECTION_MANIFEST_FILE).is_file()
    ):
        raise CoreEvaluationError("PrepareReduced must complete before this action")
    selected = read_jsonl(paths.selected_cases)
    validate_selected_panel(selected)
    manifest = read_json(paths.root / SELECTION_MANIFEST_FILE)
    if manifest.get("selected_case_sha256") != EXPECTED_SELECTED_CASE_SHA256:
        raise CoreEvaluationError("selection manifest identity differs")
    if manifest.get("authorization_identity_sha256") != gate.get(
        "authorization_identity_sha256"
    ):
        raise CoreEvaluationError("selection is bound to another Prompt-4 freeze")
    registry = ensure_c_drive(
        str(gate["decision_policy_registry"]["path"]),  # type: ignore[index]
        label="decision-policy registry",
        must_exist=True,
    )
    return paths, selected, registry


def _validate_stage_manifest(
    root: Path,
    *,
    stage: str,
    selected: Sequence[Mapping[str, object]],
    measurement_mode: str,
    expected_job_count: int,
    registry_path: Path,
) -> dict[str, object]:
    path = root / "campaign_manifest.json"
    if not path.is_file():
        raise CoreEvaluationError(f"campaign is not prepared: {path}")
    value = read_json(path)
    if value.get("campaign_stage") != stage:
        raise CoreEvaluationError(f"campaign stage differs: {root}")
    if value.get("selected_pipeline_ids") != list(matrix().pipeline_ids):
        raise CoreEvaluationError("campaign does not contain exact all-18 pipelines")
    if value.get("measurement_modes") != [measurement_mode]:
        raise CoreEvaluationError("campaign measurement mode differs")
    expected_ids = [
        case_id(row)
        for row in sorted(
            selected,
            key=lambda row: (
                str(row.get("split") or row.get("partition") or ""),
                f"{row.get('source_key') or ''}:{row.get('scoring_stratum') or 'default'}",
                case_id(row),
            ),
        )
    ]
    if value.get("selected_case_ids") != expected_ids:
        raise CoreEvaluationError("campaign selected cases differ")
    if int(value.get("job_count") or 0) != expected_job_count:
        raise CoreEvaluationError(
            f"campaign job count differs: expected {expected_job_count}"
        )
    if value.get("decision_policy_registry_sha256") != sha256_file(registry_path):
        raise CoreEvaluationError("campaign challenger policy registry differs")
    if (
        str(value.get("full_protocol_id") or "")
        != "full_speech_pipeline_v1_b0c88389194b"
    ):
        raise CoreEvaluationError("full protocol identity differs")
    return value


def _validate_terminal_jobs(
    root: Path, *, expected_job_count: int
) -> dict[str, object]:
    manifest = read_json(root / "campaign_manifest.json")
    store = EvaluationStateStore(root / "campaign.sqlite3")
    store.assert_integrity()
    rows = store.list_jobs()
    if len(rows) != expected_job_count:
        raise CoreEvaluationError("campaign database job count differs")
    nonterminal = [
        row.spec.job_id for row in rows if row.state not in {"complete", "failed"}
    ]
    if nonterminal:
        raise CoreEvaluationError(
            f"campaign has {len(nonterminal)} nonterminal jobs; resume before analysis"
        )
    complete = [row for row in rows if row.state == "complete"]
    explicit = [row for row in rows if row.state == "failed"]
    results_root = _results_root(root, manifest)
    reusable = 0
    from app.full_pipeline_evaluation.results import validate_result_tree

    for row in complete:
        result_root = results_root / row.spec.result_relative_path
        report = validate_result_tree(
            result_root, expected_reuse_identity=row.spec.reuse_identity
        )
        if not report.reusable:
            raise CoreEvaluationError(
                f"complete result is not checksum-reusable: {row.spec.job_id}"
            )
        if row.result_sha256 != sha256_file(result_root / "checksums.json"):
            raise CoreEvaluationError(
                f"result/database checksum differs: {row.spec.job_id}"
            )
        reusable += 1
    attempts = {str(row["job_id"]): row for row in store.attempt_rows()}
    for row in explicit:
        if not row.last_error and row.spec.job_id not in attempts:
            raise CoreEvaluationError(
                f"failed job lacks explicit failure evidence: {row.spec.job_id}"
            )
    return {
        "job_count": len(rows),
        "complete_result_count": len(complete),
        "checksum_reusable_result_count": reusable,
        "explicit_failure_count": len(explicit),
        "nonterminal_job_count": 0,
    }


def _bind_local_result_paths(paths: Layout, campaign_root: Path, name: str) -> None:
    manifest = read_json(campaign_root / "campaign_manifest.json")
    result_root = ensure_c_drive(
        paths.results / name / str(manifest["campaign_id"]),
        label=f"Prompt-5 {name} result root",
    )
    value = {
        "schema_version": "full-pipeline-evaluation-paths.v1",
        "campaign_id": manifest["campaign_id"],
        "workspace_root": str(campaign_root.resolve()),
        "results_root": str(result_root),
        "summary_root": str((paths.report / name).resolve()),
    }
    write_json_atomic(campaign_root / "campaign_paths.json", value)


def _results_root(root: Path, manifest: Mapping[str, object]) -> Path:
    value = read_json(root / "campaign_paths.json")
    result = ensure_c_drive(
        str(value.get("results_root") or ""), label="campaign results", must_exist=True
    )
    return result


def _reference_paths() -> tuple[Path, ...]:
    paths = (
        DEFAULT_PROTOCOL_ROOT
        / "evaluation/references/speaker_attributed_transcript.jsonl",
        DEFAULT_PROTOCOL_ROOT / "evaluation/identity/identity_overlays.jsonl",
        DEFAULT_PROTOCOL_ROOT / "evaluation/enrollment/enrollment_registry.jsonl",
    )
    return tuple(
        ensure_c_drive(path, label="prepared held-out reference", must_exist=True)
        for path in paths
    )


def _validate_material_paths(selected: Sequence[Mapping[str, object]]) -> None:
    checked: set[str] = set()
    for row in selected:
        logical = str(row.get("audio_logical_path") or "")
        if logical in checked:
            continue
        checked.add(logical)
        namespace = str(row.get("audio_namespace") or "tool_root")
        physical = (
            resolve_data_path_from_logical(logical)
            if namespace == "data_root"
            else TOOL_ROOT / logical
        )
        ensure_c_drive(physical, label="selected input audio", must_exist=True)


def _resource_case(selected: Sequence[Mapping[str, object]]) -> dict[str, object]:
    rows = [
        dict(row)
        for row in selected
        if row.get("source_key") == "product_v2"
        and row.get("gallery_primary") is True
        and str(row.get("gallery_requested_size")) == "10"
        and str(row.get("overlay_id")) == "MIXED_KNOWN_UNKNOWN"
    ]
    if not rows:
        raise CoreEvaluationError("resource representative Product V2 stratum is empty")
    return min(
        rows,
        key=lambda row: sha256_bytes(
            f"prompt5_resource_serial_v1|{SELECTION_SEED}|{case_id(row)}".encode(
                "utf-8"
            )
        ),
    )


def _source_identity() -> str:
    root = Path(__file__).resolve().parent
    entries = {path.name: sha256_file(path) for path in sorted(root.glob("*.py"))}
    return sha256_bytes(canonical_json_bytes(entries))
