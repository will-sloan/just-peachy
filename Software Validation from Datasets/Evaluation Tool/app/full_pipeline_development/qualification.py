"""Deterministic, development-only qualification contracts for all 18 pipelines.

This module does not load a model or run a smoke.  It declares the exact smoke
evidence that a runtime orchestrator must publish, seals that evidence, and
validates it (including referenced file hashes) before development reporting or
freezing may proceed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import (
    MATRIX_PATH,
    RUNTIME_CONFIG_PATH,
)
from app.full_pipeline_evaluation.protocol import DEFAULT_PROTOCOL_ROOT


QUALIFICATION_PLAN_SCHEMA_VERSION = "full-pipeline-development-qualification-plan.v1"
QUALIFICATION_RECORD_SCHEMA_VERSION = "full-pipeline-integrated-smoke-evidence.v1"
QUALIFICATION_BUNDLE_SCHEMA_VERSION = "full-pipeline-development-qualification.v1"
QUALIFICATION_VALIDATION_SCHEMA_VERSION = (
    "full-pipeline-development-qualification-validation.v1"
)
TECHNICAL_CHECKPOINT_DURATION_SEC = 0.50
REQUIRED_CHECKS = (
    "assets",
    "environment",
    "minimum_duration",
    "native_streaming_asr",
    "segmentation",
    "diarization_embedding",
    "clustering",
    "identity_backend",
    "enrollment_profile",
    "known_unknown_decision",
    "labelled_transcript",
    "event_log",
    "restart",
    "clean_shutdown",
    "cold_vs_shared_equivalence",
)
FROZEN_ANCHOR_LABELS = frozenset({"H2", "H4", "H5"})


class QualificationError(RuntimeError):
    """A development qualification contract is incomplete or inconsistent."""


def build_qualification_plan(
    *,
    matrix_path: Path = MATRIX_PATH,
    runtime_config_path: Path = RUNTIME_CONFIG_PATH,
    protocol_root: Path = DEFAULT_PROTOCOL_ROOT,
) -> dict[str, object]:
    """Build exact expected identities and evidence templates for 18 smokes."""

    resolved = FullPipelineMatrix(matrix_path, runtime_config_path)
    shared_segmentation_asset = resolved.matrix.get("shared_segmentation_asset")
    if not isinstance(shared_segmentation_asset, Mapping):
        raise QualificationError("matrix lacks the shared segmentation asset")
    protocol_summary = _json(Path(protocol_root) / "protocol_summary.json")
    development = protocol_summary.get("development_identity")
    if not isinstance(development, Mapping):
        raise QualificationError("protocol summary lacks the development identity")
    development_sha256 = _sha256(
        development.get("identity_sha256"), "development protocol identity"
    )
    protocol_id = str(protocol_summary.get("protocol_id") or "")
    if not protocol_id:
        raise QualificationError("protocol summary lacks protocol_id")

    matrix_status = resolved.status()
    records: list[dict[str, object]] = []
    for pipeline_id in resolved.pipeline_ids:
        selection = resolved.resolve(pipeline_id)
        expected = _expected_contract(
            selection,
            shared_segmentation_asset=shared_segmentation_asset,
        )
        expected_sha256 = sha256_bytes(canonical_json_bytes(expected))
        records.append(
            {
                "schema_version": QUALIFICATION_RECORD_SCHEMA_VERSION,
                "pipeline_id": pipeline_id,
                "aliases": {
                    "asr": selection.asr_alias,
                    "anonymous_diarization": selection.diarization_alias,
                    "identity": selection.identity_alias,
                    "hybrid": selection.hybrid_label,
                },
                "frozen_anchor": selection.hybrid_label in FROZEN_ANCHOR_LABELS,
                "split": "development",
                "protocol_id": protocol_id,
                "development_identity_sha256": development_sha256,
                "pipeline_config_sha256": selection.pipeline_config_sha256,
                "expected_contract": expected,
                "expected_contract_sha256": expected_sha256,
                "required_checks": list(REQUIRED_CHECKS),
                "required_actual_short_runtime_count": 1,
                "required_cold_execution_count": 1,
                "required_shared_execution_count": 1,
                "evaluation_material_inspected": False,
                "qualification_status": "PENDING",
            }
        )

    core = {
        "schema_version": QUALIFICATION_PLAN_SCHEMA_VERSION,
        "protocol_id": protocol_id,
        "development_identity_sha256": development_sha256,
        "matrix_sha256": matrix_status["matrix_sha256"],
        "runtime_config_sha256": matrix_status["runtime_config_sha256"],
        "pipeline_count": len(records),
        "records": records,
        "evaluation_material_inspected": False,
        "inference_started": False,
    }
    return {**core, "plan_identity_sha256": sha256_bytes(canonical_json_bytes(core))}


def write_qualification_plan(path: Path, plan: Mapping[str, object]) -> Path:
    """Atomically write a structurally valid plan."""

    _validate_plan(plan)
    return write_json_atomic(Path(path), dict(plan))


def build_qualification_bundle(
    plan: Mapping[str, object],
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Seal runtime-produced records without claiming that their files validate."""

    _validate_plan(plan)
    sealed: list[dict[str, object]] = []
    for raw in sorted(records, key=lambda row: str(row.get("pipeline_id") or "")):
        record = dict(raw)
        record.pop("record_identity_sha256", None)
        record["record_identity_sha256"] = sha256_bytes(canonical_json_bytes(record))
        sealed.append(record)
    core = {
        "schema_version": QUALIFICATION_BUNDLE_SCHEMA_VERSION,
        "status": (
            "PASS"
            if len(sealed) == 18
            and all(row.get("qualification_status") == "PASS" for row in sealed)
            else "FAIL"
        ),
        "protocol_id": plan["protocol_id"],
        "development_identity_sha256": plan["development_identity_sha256"],
        "matrix_sha256": plan["matrix_sha256"],
        "runtime_config_sha256": plan["runtime_config_sha256"],
        "plan_identity_sha256": plan["plan_identity_sha256"],
        "pipeline_count": len(sealed),
        "records": sealed,
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
    }
    return {
        **core,
        "qualification_result_sha256": sha256_bytes(canonical_json_bytes(core)),
    }


def write_qualification_bundle(path: Path, bundle: Mapping[str, object]) -> Path:
    """Atomically write a sealed qualification bundle."""

    return write_json_atomic(Path(path), dict(bundle))


def validate_qualification_bundle(
    bundle: Mapping[str, object] | Path,
    *,
    plan: Mapping[str, object] | Path | None = None,
    evidence_root: Path | None = None,
    verify_evidence_files: bool = True,
) -> dict[str, object]:
    """Validate exact identities, 18 smoke records, firewall, and evidence bytes.

    Validation is model-free.  When ``verify_evidence_files`` is true (the
    default), every check must cite at least one checksum-valid relative file.
    """

    bundle_path = Path(bundle).resolve() if isinstance(bundle, Path) else None
    value = _json(bundle_path) if bundle_path is not None else dict(bundle)
    if plan is None:
        expected = build_qualification_plan()
    elif isinstance(plan, Path):
        expected = _json(plan.resolve())
    else:
        expected = dict(plan)
    errors: list[str] = []
    warnings: list[str] = []
    try:
        _validate_plan(expected)
    except (QualificationError, KeyError, TypeError, ValueError) as exc:
        errors.append(f"qualification plan is invalid: {exc}")

    if value.get("schema_version") != QUALIFICATION_BUNDLE_SCHEMA_VERSION:
        errors.append("qualification bundle schema differs")
    if value.get("status") != "PASS":
        errors.append("qualification bundle status is not PASS")
    for field in (
        "protocol_id",
        "development_identity_sha256",
        "matrix_sha256",
        "runtime_config_sha256",
        "plan_identity_sha256",
    ):
        if value.get(field) != expected.get(field):
            errors.append(f"qualification bundle {field} differs from the plan")
    if value.get("evaluation_material_inspected") is not False:
        errors.append("qualification bundle lacks the no-evaluation attestation")
    if value.get("production_winner_selected") is not False:
        errors.append("qualification may not select a production winner")
    _reject_evaluation_material(value, errors, "qualification bundle")

    expected_records = {
        str(row["pipeline_id"]): row
        for row in _mapping_rows(expected.get("records"), "plan records", errors)
    }
    actual_rows = _mapping_rows(value.get("records"), "qualification records", errors)
    actual_records = {
        str(row.get("pipeline_id") or ""): row for row in actual_rows
    }
    if len(actual_rows) != len(actual_records):
        errors.append("qualification contains duplicate pipeline records")
    if set(actual_records) != set(expected_records) or len(actual_records) != 18:
        errors.append(
            "qualification must contain exactly the 18 planned pipeline records"
        )
    if value.get("pipeline_count") != 18:
        errors.append("qualification pipeline_count must be 18")

    root = (
        Path(evidence_root).resolve()
        if evidence_root is not None
        else (bundle_path.parent if bundle_path is not None else None)
    )
    verified_files: set[str] = set()
    for pipeline_id in sorted(set(actual_records) & set(expected_records)):
        _validate_record(
            actual_records[pipeline_id],
            expected_records[pipeline_id],
            root=root,
            verify_evidence_files=verify_evidence_files,
            verified_files=verified_files,
            errors=errors,
        )

    core = {key: item for key, item in value.items() if key != "qualification_result_sha256"}
    if value.get("qualification_result_sha256") != sha256_bytes(
        canonical_json_bytes(core)
    ):
        errors.append("qualification result identity differs")
    return {
        "schema_version": QUALIFICATION_VALIDATION_SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        "pipeline_count": len(actual_records),
        "verified_evidence_file_count": len(verified_files),
        "all_six_anchor_pipelines_integrated_smoke_passed": not errors
        and sum(
            bool(expected_records[pipeline_id].get("frozen_anchor"))
            for pipeline_id in actual_records
            if pipeline_id in expected_records
        )
        == 6,
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
        "errors": errors,
        "warnings": warnings,
        "model_inference_performed_by_validation": False,
    }


def require_valid_qualification_bundle(
    bundle: Mapping[str, object] | Path,
    *,
    plan: Mapping[str, object] | Path | None = None,
    evidence_root: Path | None = None,
    verify_evidence_files: bool = True,
) -> dict[str, object]:
    """Return validation or raise before any report/freeze action."""

    result = validate_qualification_bundle(
        bundle,
        plan=plan,
        evidence_root=evidence_root,
        verify_evidence_files=verify_evidence_files,
    )
    if not result["valid"]:
        raise QualificationError("; ".join(str(item) for item in result["errors"]))
    return result


def _expected_contract(
    selection: object,
    *,
    shared_segmentation_asset: Mapping[str, object],
) -> dict[str, object]:
    asr = dict(selection.asr)
    diarization = dict(selection.diarization)
    diar_embedding = dict(selection.diarization_embedding)
    identity = dict(selection.identity)
    segmentation_component_id = str(shared_segmentation_asset.get("asset_id") or "")
    segmentation_cache_contract_id = str(diarization.get("segmentation_id") or "")
    shared_segmentation_sha256 = _sha256(
        shared_segmentation_asset.get("installed_tree_sha256"),
        "shared segmentation asset identity",
    )
    diarization_segmentation_sha256 = _sha256(
        diarization.get("segmentation_model_asset_sha256"),
        "diarization segmentation asset identity",
    )
    if not segmentation_component_id:
        raise QualificationError("shared segmentation asset lacks asset_id")
    if not segmentation_cache_contract_id:
        raise QualificationError("diarization lacks segmentation cache contract ID")
    if shared_segmentation_sha256 != diarization_segmentation_sha256:
        raise QualificationError(
            "diarization segmentation asset differs from the shared model asset"
        )
    minimum = float(identity["minimum_duration_sec"])
    checkpoint_outcome = (
        "TECHNICALLY_VALID"
        if TECHNICAL_CHECKPOINT_DURATION_SEC >= minimum
        else "TECHNICALLY_INVALID_BELOW_BACKEND_MINIMUM"
    )
    return {
        "assets": {
            "asr": {
                "component_id": asr["component_id"],
                "config_sha256": asr["config_sha256"],
                "model_asset": dict(asr["model_asset"]),
            },
            "segmentation": {
                "asset_id": segmentation_component_id,
                "runtime_component_id": segmentation_component_id,
                "cache_contract_id": segmentation_cache_contract_id,
                "installed_tree_sha256": shared_segmentation_sha256,
            },
            "diarization_embedding": {
                "backend_id": diar_embedding["backend_id"],
                "model_identity_sha256": diar_embedding["model_identity_sha256"],
                "config_sha256": diar_embedding["config_sha256"],
            },
            "identity": {
                "backend_id": identity["backend_id"],
                "model_identity_sha256": identity["model_identity_sha256"],
                "config_sha256": identity["config_sha256"],
            },
        },
        "environments": {
            "asr": asr["environment_profile"],
            "segmentation": diarization["segmentation_environment_profile"],
            "diarization_embedding": diarization["embedding_environment_profile"],
            "identity": identity["environment_profile"],
        },
        "minimum_duration": {
            "backend_id": identity["backend_id"],
            "documented_minimum_duration_sec": minimum,
            "technical_checkpoint_duration_sec": TECHNICAL_CHECKPOINT_DURATION_SEC,
            "expected_checkpoint_outcome": checkpoint_outcome,
            "short_checkpoint_may_be_invalid_without_invalidating_pipeline": True,
        },
        "native_streaming_asr_required": True,
        "segmentation_component_id": segmentation_component_id,
        "segmentation_cache_contract_id": segmentation_cache_contract_id,
        "diarization_pipeline_id": diarization["pipeline_id"],
        "clustering_algorithm": diarization["clustering_family"],
        "identity_backend_id": identity["backend_id"],
        "enrollment_policy": dict(selection.enrollment_policy),
        "known_unknown_decision_policy_id": "full_pipeline_open_set_decision.v1",
        "labelled_transcript_required": True,
        "event_log_required": True,
        "restart_required": True,
        "clean_shutdown_required": True,
        "cold_vs_shared_equivalence_required": True,
    }


def _validate_plan(plan: Mapping[str, object]) -> None:
    if plan.get("schema_version") != QUALIFICATION_PLAN_SCHEMA_VERSION:
        raise QualificationError("qualification plan schema differs")
    rows = plan.get("records")
    if not isinstance(rows, list) or len(rows) != 18:
        raise QualificationError("qualification plan must contain exactly 18 records")
    if len({str(row.get("pipeline_id")) for row in rows if isinstance(row, Mapping)}) != 18:
        raise QualificationError("qualification plan pipeline IDs are not unique")
    core = {key: item for key, item in plan.items() if key != "plan_identity_sha256"}
    if plan.get("plan_identity_sha256") != sha256_bytes(canonical_json_bytes(core)):
        raise QualificationError("qualification plan identity differs")


def _validate_record(
    record: Mapping[str, object],
    expected: Mapping[str, object],
    *,
    root: Path | None,
    verify_evidence_files: bool,
    verified_files: set[str],
    errors: list[str],
) -> None:
    pipeline_id = str(expected["pipeline_id"])
    if record.get("schema_version") != QUALIFICATION_RECORD_SCHEMA_VERSION:
        errors.append(f"{pipeline_id}: qualification record schema differs")
    for field in (
        "pipeline_id",
        "aliases",
        "frozen_anchor",
        "split",
        "protocol_id",
        "development_identity_sha256",
        "pipeline_config_sha256",
        "expected_contract",
        "expected_contract_sha256",
    ):
        if record.get(field) != expected.get(field):
            errors.append(f"{pipeline_id}: {field} differs from the qualification plan")
    if record.get("qualification_status") != "PASS":
        errors.append(f"{pipeline_id}: qualification status is not PASS")
    if record.get("evaluation_material_inspected") is not False:
        errors.append(f"{pipeline_id}: no-evaluation attestation is absent")
    if record.get("actual_short_runtime_count") != 1:
        errors.append(f"{pipeline_id}: exactly one integrated short-runtime evidence unit required")
    if record.get("cold_execution_count") != 1 or record.get(
        "shared_execution_count"
    ) != 1:
        errors.append(f"{pipeline_id}: cold/shared execution counts must both equal one")
    duration = _finite_float(record.get("smoke_audio_duration_sec"))
    minimum = float(expected["expected_contract"]["minimum_duration"]["documented_minimum_duration_sec"])
    if duration is None or duration < minimum:
        errors.append(f"{pipeline_id}: integrated smoke audio is below backend minimum")
    if not str(record.get("smoke_case_id") or ""):
        errors.append(f"{pipeline_id}: smoke_case_id is absent")
    if not _is_sha256(record.get("source_audio_sha256")):
        errors.append(f"{pipeline_id}: source audio identity is absent")
    _reject_evaluation_material(record, errors, pipeline_id)

    checks_value = record.get("checks")
    checks = checks_value if isinstance(checks_value, Mapping) else {}
    if set(checks) != set(REQUIRED_CHECKS):
        errors.append(f"{pipeline_id}: exact qualification check coverage differs")
    for check_name in REQUIRED_CHECKS:
        raw = checks.get(check_name)
        if not isinstance(raw, Mapping):
            errors.append(f"{pipeline_id}: {check_name} evidence is absent")
            continue
        if raw.get("status") != "PASS" or not _is_sha256(raw.get("evidence_sha256")):
            errors.append(f"{pipeline_id}: {check_name} evidence did not pass")
        evidence_core = {
            key: item for key, item in raw.items() if key != "evidence_sha256"
        }
        if raw.get("evidence_sha256") != sha256_bytes(
            canonical_json_bytes(evidence_core)
        ):
            errors.append(f"{pipeline_id}: {check_name} evidence identity differs")
        if raw.get("expected_contract_sha256") != expected.get(
            "expected_contract_sha256"
        ):
            errors.append(f"{pipeline_id}: {check_name} is not bound to the exact contract")
        refs = raw.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{pipeline_id}: {check_name} cites no evidence files")
        else:
            for ref in refs:
                _verify_evidence_ref(
                    pipeline_id,
                    check_name,
                    ref,
                    root=root,
                    verify=verify_evidence_files,
                    verified_files=verified_files,
                    errors=errors,
                )

    minimum_check = checks.get("minimum_duration")
    if isinstance(minimum_check, Mapping):
        contract = expected["expected_contract"]["minimum_duration"]
        for field in (
            "documented_minimum_duration_sec",
            "technical_checkpoint_duration_sec",
            "checkpoint_outcome",
        ):
            expected_field = (
                "expected_checkpoint_outcome"
                if field == "checkpoint_outcome"
                else field
            )
            if minimum_check.get(field) != contract.get(expected_field):
                errors.append(f"{pipeline_id}: minimum-duration {field} differs")
        if minimum_check.get("full_pipeline_invalidated_by_checkpoint") is not False:
            errors.append(
                f"{pipeline_id}: 0.50-s checkpoint improperly invalidates the pipeline"
            )
    equivalence = checks.get("cold_vs_shared_equivalence")
    if isinstance(equivalence, Mapping):
        if equivalence.get("semantically_equivalent") is not True:
            errors.append(f"{pipeline_id}: cold/shared semantic equivalence failed")
        if equivalence.get("cold_execution_origin") != "primary_computed" or equivalence.get(
            "shared_execution_origin"
        ) not in {"shared_worker_pool", "accuracy_replayed"}:
            errors.append(f"{pipeline_id}: cold/shared execution provenance differs")
        if (
            not _is_sha256(equivalence.get("cold_semantic_result_sha256"))
            or equivalence.get("cold_semantic_result_sha256")
            != equivalence.get("shared_semantic_result_sha256")
        ):
            errors.append(f"{pipeline_id}: cold/shared semantic result identities differ")
        if (
            not _is_sha256(equivalence.get("cold_event_sequence_sha256"))
            or equivalence.get("cold_event_sequence_sha256")
            != equivalence.get("shared_event_sequence_sha256")
        ):
            errors.append(f"{pipeline_id}: cold/shared event sequences differ")

    core = {key: item for key, item in record.items() if key != "record_identity_sha256"}
    if record.get("record_identity_sha256") != sha256_bytes(canonical_json_bytes(core)):
        errors.append(f"{pipeline_id}: qualification record identity differs")


def _verify_evidence_ref(
    pipeline_id: str,
    check_name: str,
    raw: object,
    *,
    root: Path | None,
    verify: bool,
    verified_files: set[str],
    errors: list[str],
) -> None:
    if not isinstance(raw, Mapping):
        errors.append(f"{pipeline_id}: {check_name} evidence reference is invalid")
        return
    logical = str(raw.get("path") or "").replace("\\", "/")
    expected_sha = raw.get("sha256")
    if not logical or logical.startswith("/") or ".." in Path(logical).parts:
        errors.append(f"{pipeline_id}: {check_name} evidence path is not portable")
        return
    if not _is_sha256(expected_sha):
        errors.append(f"{pipeline_id}: {check_name} evidence file SHA-256 is invalid")
        return
    if not verify:
        return
    if root is None:
        errors.append(f"{pipeline_id}: evidence root is required for file verification")
        return
    target = (root / logical).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        errors.append(f"{pipeline_id}: {check_name} evidence escapes its root")
        return
    if not target.is_file():
        errors.append(f"{pipeline_id}: {check_name} evidence file is missing: {logical}")
        return
    if sha256_file(target).lower() != str(expected_sha).lower():
        errors.append(f"{pipeline_id}: {check_name} evidence file hash differs: {logical}")
        return
    verified_files.add(logical)


def _reject_evaluation_material(
    value: Mapping[str, object], errors: list[str], label: str
) -> None:
    for path, item in _walk(value):
        key = path[-1].casefold() if path else ""
        if key in {"split", "partition"} and str(item).casefold() == "evaluation":
            errors.append(f"{label}: evaluation split material is forbidden")
        if key == "evaluation_material_inspected" and item is not False:
            errors.append(f"{label}: evaluation material was inspected")
        if key in {
            "evaluation_case_ids",
            "evaluation_result_paths",
            "evaluation_observations",
            "heldout_evaluation_rows",
        }:
            is_empty = item is None or item is False or item == "" or item == ()
            if isinstance(item, (list, dict, set)):
                is_empty = not item
            if not is_empty:
                errors.append(f"{label}: nonempty evaluation evidence is forbidden")


def _walk(value: object, path: tuple[str, ...] = ()) -> Sequence[tuple[tuple[str, ...], object]]:
    rows: list[tuple[tuple[str, ...], object]] = [(path, value)]
    if isinstance(value, Mapping):
        for key, item in value.items():
            rows.extend(_walk(item, (*path, str(key))))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk(item, (*path, str(index))))
    return rows


def _mapping_rows(
    value: object, label: str, errors: list[str]
) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    rows = [row for row in value if isinstance(row, Mapping)]
    if len(rows) != len(value):
        errors.append(f"{label} contains a non-object row")
    return rows


def _json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise QualificationError(f"required JSON is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QualificationError(f"JSON root must be an object: {path}")
    return value


def _finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _is_sha256(value: object) -> bool:
    text = str(value or "").casefold()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _sha256(value: object, label: str) -> str:
    if not _is_sha256(value):
        raise QualificationError(f"{label} must be a SHA-256 digest")
    return str(value).casefold()


__all__ = [
    "QUALIFICATION_BUNDLE_SCHEMA_VERSION",
    "QUALIFICATION_PLAN_SCHEMA_VERSION",
    "QUALIFICATION_RECORD_SCHEMA_VERSION",
    "QualificationError",
    "REQUIRED_CHECKS",
    "TECHNICAL_CHECKPOINT_DURATION_SEC",
    "build_qualification_bundle",
    "build_qualification_plan",
    "require_valid_qualification_bundle",
    "validate_qualification_bundle",
    "write_qualification_bundle",
    "write_qualification_plan",
]
