"""Immutable all-18 development configuration and Tier-B freeze helpers.

The helpers are intentionally model-free and evaluation-blind.  They may run
only after the development policy registry and complete development result set
exist.  No function in this module selects a Tier-C production winner.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from .policies import (
    FROZEN_ANCHOR_LABELS,
    FROZEN_HYBRID_PROTOCOL_ID,
    FROZEN_HYBRID_SELECTION_SHA256,
    audit_frozen_anchor_policies,
    challenger_pipeline_ids,
    resolve_decision_policy_contract,
    validate_development_policy_registry,
)
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    sha256_bytes,
    sha256_file,
    write_bytes_atomic,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import (
    EVALUATION_ROOT,
    MATRIX_PATH,
    RUNTIME_CONFIG_PATH,
    matrix,
)


PIPELINE_FREEZE_SCHEMA_VERSION = "full-pipeline-development-config-freeze.v1"
EXTENDED_SET_SCHEMA_VERSION = "full-pipeline-tier-b-development-set.v1"
MANDATORY_EXTENDED_PIPELINES = (
    "fullpipe_v1_ao_dr_ir",  # AO-H2
    "fullpipe_v1_ag_dr_ir",  # AG-H2
    "fullpipe_v1_ao_dw_ir",  # AO-H4
    "fullpipe_v1_ag_dw_ir",  # AG-H4
    "fullpipe_v1_ao_dr_ie",  # AO-H5
    "fullpipe_v1_ag_dr_ie",  # AG-H5
)
PARETO_AXES = (
    "wrong_known_rate",
    "stranger_false_known_rate",
    "speaker_attributed_wer",
    "stable_name_latency_sec",
    "total_rtf",
    "peak_rss_bytes",
)
REQUIRED_ANCHOR_RUNTIME_CHECKS = (
    "correct_diarization_embedding_provenance",
    "predicted_overlap_excluded_from_primary_identity",
    "product_v2_probe_consistency_semantics",
    "product_v2_hysteresis_semantics",
    "decision_policy_hash_is_not_enrollment_hash",
    "all_six_anchor_pipelines_integrated_smoke_passed",
)


class DevelopmentFreezeError(RuntimeError):
    """An all-18 freeze or development selection invariant failed."""


def baseline_alignment_buffering_policy() -> dict[str, object]:
    """Return the current, untuned timestamp-fusion/buffering identity."""

    core = {
        "policy_id": "full_pipeline_alignment_buffering.development.v1:baseline",
        "development_tuned": False,
        "audio_frame_duration_ms": 100,
        "asr_partial_update_interval_ms": 500,
        "diarization_rolling_analysis_window_sec": 10.0,
        "diarization_rolling_step_sec": 0.75,
        "diarization_algorithmic_lookahead_sec": 5.0,
        "transcript_alignment": "source_timestamp_overlap",
        "ambiguous_multi_speaker_span": "remain_explicitly_ambiguous",
        "identity_relabel": "causal_revision_only",
        "source_clock_required": True,
    }
    return {**core, "identity_sha256": sha256_bytes(canonical_json_bytes(core))}


def freeze_all_pipeline_configs(
    *,
    policy_registry: Mapping[str, object],
    protocol_id: str,
    development_protocol_sha256: str,
    development_result_set_sha256: str,
    output_root: Path,
    runtime_anchor_qualification: Mapping[str, object],
    alignment_buffering_policy: Mapping[str, object] | None = None,
    evaluation_root: Path = EVALUATION_ROOT,
) -> dict[str, object]:
    """Write exactly 18 checksum-bound YAML configurations once.

    ``output_root`` must be absent or empty.  A caller cannot overwrite a prior
    scientific freeze.  Challenger entries are copied from the exact-pipeline
    policy registry; anchor entries bind the authoritative frozen Product V2
    selection without recalibration.
    """

    validate_development_policy_registry(policy_registry)
    expected_challengers = set(challenger_pipeline_ids())
    raw_entries = policy_registry["entries"]
    assert isinstance(raw_entries, list)
    registry_entries = {
        str(row["pipeline_id"]): dict(row)
        for row in raw_entries
        if isinstance(row, Mapping)
    }
    if set(registry_entries) != expected_challengers:
        missing = sorted(expected_challengers - set(registry_entries))
        extra = sorted(set(registry_entries) - expected_challengers)
        raise DevelopmentFreezeError(
            f"all-18 freeze requires all 12 challengers; missing={missing}, extra={extra}"
        )
    protocol_hash = _sha256(development_protocol_sha256, "development protocol")
    result_hash = _sha256(development_result_set_sha256, "development result set")
    root = Path(evaluation_root).resolve()
    anchor_audit = audit_frozen_anchor_policies(evaluation_root=root)
    if anchor_audit["status"] != "PASS":
        raise DevelopmentFreezeError(
            "frozen anchor audit failed: " + "; ".join(anchor_audit["errors"])
        )
    _validate_anchor_runtime_qualification(runtime_anchor_qualification)
    alignment = dict(alignment_buffering_policy or baseline_alignment_buffering_policy())
    _validate_alignment_policy(alignment)
    destination = Path(output_root).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"pipeline freeze directory is immutable: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    matrix_doc = _yaml(root / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml")
    runtime_doc = _yaml(root / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml")
    resolved = matrix()
    code_identity = _result_affecting_code_identity(root)
    written: list[str] = []
    for pipeline_id in resolved.pipeline_ids:
        selection = resolved.resolve(pipeline_id)
        if selection.hybrid_label in FROZEN_ANCHOR_LABELS:
            decision_policy: Mapping[str, object] = resolve_decision_policy_contract(
                pipeline_id, realized_gallery_size=10
            )
        else:
            decision_policy = {
                **registry_entries[pipeline_id],
                "decision_policy_sha256": registry_entries[pipeline_id][
                    "calibration_identity_sha256"
                ],
                "calibration_protocol_id": policy_registry["protocol_id"],
                "calibration_result_sha256": registry_entries[pipeline_id][
                    "calibration_identity_sha256"
                ],
                "target_fpir": 0.01,
                "threshold_scope": "exact_pipeline_and_frozen_gallery_request",
            }
        core = {
            "schema_version": PIPELINE_FREEZE_SCHEMA_VERSION,
            "status": "IMMUTABLE_DEVELOPMENT_FREEZE",
            "pipeline_id": pipeline_id,
            "pipeline_config_sha256_before_development_freeze": (
                selection.pipeline_config_sha256
            ),
            "protocol_id": protocol_id,
            "development_protocol_sha256": protocol_hash,
            "development_result_set_sha256": result_hash,
            "evaluation_material_inspected": False,
            "evaluation_retuning_allowed": False,
            "production_winner_selected": False,
            "runtime_anchor_qualification": dict(runtime_anchor_qualification),
            "aliases": {
                "asr": selection.asr_alias,
                "anonymous_diarization": selection.diarization_alias,
                "identity": selection.identity_alias,
                "hybrid": selection.hybrid_label,
            },
            "asr": {
                "component": dict(selection.asr),
                "runtime": dict(runtime_doc["asr"]),
                "streaming_policy": dict(matrix_doc["policies"]["streaming"]),
            },
            "segmentation": {
                "shared_asset": dict(matrix_doc["shared_segmentation_asset"]),
                "runtime": {
                    key: value
                    for key, value in runtime_doc["incremental_diarization"].items()
                    if key
                    in {
                        "policy_id",
                        "rolling_analysis_window_sec",
                        "rolling_step_sec",
                        "history_context_sec",
                        "algorithmic_lookahead_sec",
                        "flush_at_end_of_input",
                        "future_evidence_used",
                    }
                },
            },
            "anonymous_diarization_and_clustering": {
                "component": dict(selection.diarization),
                "runtime": dict(runtime_doc["incremental_diarization"]),
            },
            "identity_policy": dict(decision_policy),
            "enrollment_policy": {
                **dict(selection.enrollment_policy),
                "clip_materialization": "first_three_full_reserved_clips",
                "audio_padding": False,
                "target_duration_is_selection_guidance_not_trimming": True,
            },
            "transcript_alignment_and_buffering": alignment,
            "ui_label_policy": {
                "unknown_labels": "stable_session_local_Unknown_N",
                "label_states": ["unknown", "tentative", "confirmed"],
                "tentative_visible": True,
                "raw_score_displayed_as_confidence_percentage": False,
                "retroactive_changes_require_causal_revision": True,
            },
            "model_assets": _model_asset_identity(matrix_doc, selection),
            "source_hashes": {
                "matrix_sha256": sha256_file(MATRIX_PATH),
                "runtime_config_sha256": sha256_file(RUNTIME_CONFIG_PATH),
                "development_policy_registry_sha256": policy_registry[
                    "registry_identity_sha256"
                ],
                "frozen_hybrid_protocol_id": FROZEN_HYBRID_PROTOCOL_ID,
                "frozen_hybrid_selection_sha256": FROZEN_HYBRID_SELECTION_SHA256,
            },
            "result_affecting_code": code_identity,
        }
        document = {
            **core,
            "freeze_identity_sha256": sha256_bytes(canonical_json_bytes(core)),
        }
        relative = f"{pipeline_id}.yaml"
        _write_yaml_once(destination / relative, document)
        written.append(relative)

    checksums = checksum_map(destination)
    write_json_atomic(
        destination / "checksums.json",
        {
            "schema_version": "full-pipeline-development-config-checksums.v1",
            "pipeline_count": len(written),
            "entries": checksums,
        },
    )
    return {
        "schema_version": "full-pipeline-development-freeze-result.v1",
        "status": "PASS",
        "pipeline_count": len(written),
        "output_root": str(destination),
        "pipeline_files": written,
        "checksums_path": str(destination / "checksums.json"),
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
    }


def build_extended_set(
    development_rows: Sequence[Mapping[str, object]],
    *,
    maximum_additional_challengers: int = 2,
) -> dict[str, object]:
    """Predeclare mandatory six plus up to two development Pareto challengers."""

    if maximum_additional_challengers not in {0, 1, 2}:
        raise ValueError("maximum_additional_challengers must be 0, 1, or 2")
    normalized = [_normalize_development_row(row) for row in development_rows]
    by_id = {str(row["pipeline_id"]): row for row in normalized}
    if len(by_id) != 18:
        raise DevelopmentFreezeError(
            "extended-set selection requires one complete development row for all 18 pipelines"
        )
    nondominated = [
        row
        for row in normalized
        if not any(
            _dominates(other, row)
            for other in normalized
            if other["pipeline_id"] != row["pipeline_id"]
        )
    ]
    candidates = [
        row
        for row in nondominated
        if row["pipeline_id"] not in MANDATORY_EXTENDED_PIPELINES
    ]
    candidates.sort(
        key=lambda row: tuple(float(row[axis]) for axis in PARETO_AXES)
        + (str(row["pipeline_id"]),)
    )
    selected = candidates[:maximum_additional_challengers]
    core = {
        "schema_version": EXTENDED_SET_SCHEMA_VERSION,
        "status": "FROZEN_DEVELOPMENT_ONLY",
        "selection_method": "unweighted_pareto_then_locked_lexicographic_priorities",
        "weighted_composite_score_used": False,
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
        "pareto_axes": list(PARETO_AXES),
        "mandatory_pipeline_ids": list(MANDATORY_EXTENDED_PIPELINES),
        "additional_challenger_limit": maximum_additional_challengers,
        "additional_challenger_pipeline_ids": [
            str(row["pipeline_id"]) for row in selected
        ],
        "extended_pipeline_ids": [
            *MANDATORY_EXTENDED_PIPELINES,
            *(str(row["pipeline_id"]) for row in selected),
        ],
        "development_nondominated_pipeline_ids": sorted(
            str(row["pipeline_id"]) for row in nondominated
        ),
    }
    return {**core, "identity_sha256": sha256_bytes(canonical_json_bytes(core))}


def write_extended_set(path: Path, value: Mapping[str, object]) -> Path:
    """Write the immutable development Tier-B declaration."""

    if value.get("schema_version") != EXTENDED_SET_SCHEMA_VERSION:
        raise DevelopmentFreezeError("invalid extended-set schema")
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"extended set is immutable: {target}")
    return _write_yaml_once(target, value)


def _normalize_development_row(raw: Mapping[str, object]) -> dict[str, object]:
    row = dict(raw)
    pipeline_id = str(row.get("pipeline_id") or "")
    if pipeline_id not in set(matrix().pipeline_ids):
        raise DevelopmentFreezeError(f"unknown pipeline in development summary: {pipeline_id}")
    if str(row.get("split") or "development") != "development":
        raise DevelopmentFreezeError("evaluation row rejected from extended-set selection")
    if row.get("evaluation_material_inspected") is not False:
        raise DevelopmentFreezeError("development row lacks no-evaluation attestation")
    if str(row.get("qualification_status") or "") != "VALID":
        raise DevelopmentFreezeError(f"pipeline is not technically valid: {pipeline_id}")
    for axis in PARETO_AXES:
        try:
            value = float(row[axis])
        except (KeyError, TypeError, ValueError) as exc:
            raise DevelopmentFreezeError(
                f"computed Pareto metric {axis} missing for {pipeline_id}"
            ) from exc
        if not math.isfinite(value):
            raise DevelopmentFreezeError(f"non-finite {axis} for {pipeline_id}")
        row[axis] = value
    return row


def _dominates(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    values = [
        (float(left[axis]), float(right[axis])) for axis in PARETO_AXES
    ]
    return all(a <= b for a, b in values) and any(a < b for a, b in values)


def _validate_alignment_policy(value: Mapping[str, object]) -> None:
    if not str(value.get("policy_id") or "").strip():
        raise DevelopmentFreezeError("alignment/buffering policy_id is required")
    identity = value.get("identity_sha256")
    core = {key: item for key, item in value.items() if key != "identity_sha256"}
    expected = sha256_bytes(canonical_json_bytes(core))
    if identity != expected:
        raise DevelopmentFreezeError("alignment/buffering policy checksum mismatch")


def _validate_anchor_runtime_qualification(value: Mapping[str, object]) -> None:
    if value.get("schema_version") != "full-pipeline-anchor-runtime-qualification.v1":
        raise DevelopmentFreezeError("anchor runtime qualification schema missing")
    if value.get("status") != "PASS":
        raise DevelopmentFreezeError("anchor runtime qualification did not pass")
    if value.get("evaluation_material_inspected") is not False:
        raise DevelopmentFreezeError("anchor qualification inspected evaluation material")
    _sha256(value.get("qualification_result_sha256"), "anchor qualification result")
    failures = [key for key in REQUIRED_ANCHOR_RUNTIME_CHECKS if value.get(key) is not True]
    if failures:
        raise DevelopmentFreezeError(
            "anchor runtime semantics are not exact: " + ", ".join(failures)
        )


def _model_asset_identity(
    matrix_doc: Mapping[str, object], selection: object
) -> dict[str, object]:
    asr = dict(selection.asr)
    diar = dict(selection.diarization)
    identity = dict(selection.identity)
    axes = matrix_doc["axes"]
    diar_identity_matches = [
        dict(row)
        for row in axes["identity"].values()
        if isinstance(row, Mapping)
        and str(row.get("backend_id")) == str(diar["embedding_backend_id"])
    ]
    if len(diar_identity_matches) != 1:
        raise DevelopmentFreezeError("diarization embedding asset mapping is ambiguous")
    diar_identity = diar_identity_matches[0]
    return {
        "asr": {
            "asset": dict(asr["model_asset"]),
            "config_sha256": asr["config_sha256"],
        },
        "segmentation": dict(matrix_doc["shared_segmentation_asset"]),
        "diarization_embedding": {
            "backend_id": diar_identity["backend_id"],
            "model_id": diar_identity["model_id"],
            "model_identity_sha256": diar_identity["model_identity_sha256"],
            "model_asset_sha256": diar_identity.get("model_asset_sha256"),
            "config_sha256": diar_identity["config_sha256"],
        },
        "identity_embedding": {
            "backend_id": identity["backend_id"],
            "model_id": identity["model_id"],
            "model_identity_sha256": identity["model_identity_sha256"],
            "model_asset_sha256": identity.get("model_asset_sha256"),
            "config_sha256": identity["config_sha256"],
        },
    }


def _result_affecting_code_identity(root: Path) -> dict[str, object]:
    files = tuple(sorted((root / "app/full_pipeline").glob("*.py"))) + tuple(
        sorted((root / "app/full_pipeline_evaluation").glob("*.py"))
    ) + (
        root / "app/inference_pipeline/asr/sherpa_onnx_adapter.py",
        root / "app/full_pipeline_development/policies.py",
        root / "app/full_pipeline_development/shared_execution.py",
    )
    entries = {
        path.relative_to(root).as_posix(): sha256_file(path) for path in files
    }
    return {
        "sha256": sha256_bytes(canonical_json_bytes(entries)),
        "files": entries,
    }


def _write_yaml_once(path: Path, value: Mapping[str, object]) -> Path:
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"immutable artifact already exists: {target}")
    payload = yaml.safe_dump(
        dict(value), sort_keys=True, allow_unicode=True
    ).encode("utf-8")
    return write_bytes_atomic(target, payload)


def _yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise DevelopmentFreezeError(f"YAML root is not an object: {path}")
    return value


def _sha256(value: object, label: str) -> str:
    text = str(value or "").casefold()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 hex digest")
    return text
