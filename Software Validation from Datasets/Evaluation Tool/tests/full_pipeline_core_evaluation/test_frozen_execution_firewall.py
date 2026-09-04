from __future__ import annotations

from pathlib import Path
import shutil

import pytest
import yaml

from app.full_pipeline_core_evaluation.gate import (
    CoreEvaluationError,
    _validate_frozen_configs,
)
from app.full_pipeline_development.freeze import freeze_all_pipeline_configs
from app.full_pipeline_development.policies import (
    OBSERVATION_SCHEMA_VERSION,
    build_development_policy_registry,
    challenger_pipeline_ids,
)
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import matrix


SHA = "a" * 64
ANCHOR_QUALIFICATION = {
    "schema_version": "full-pipeline-anchor-runtime-qualification.v1",
    "status": "PASS",
    "evaluation_material_inspected": False,
    "qualification_result_sha256": "c" * 64,
    "correct_diarization_embedding_provenance": True,
    "predicted_overlap_excluded_from_primary_identity": True,
    "product_v2_probe_consistency_semantics": True,
    "product_v2_hysteresis_semantics": True,
    "decision_policy_hash_is_not_enrollment_hash": True,
    "all_six_anchor_pipelines_integrated_smoke_passed": True,
}


def _observation(pipeline_id: str, ordinal: int) -> dict[str, object]:
    selection = matrix().resolve(pipeline_id)
    return {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "pipeline_id": pipeline_id,
        "hybrid_label": selection.hybrid_label,
        "identity_backend_id": selection.identity["backend_id"],
        "protocol_id": "full_speech_pipeline_v1_synthetic_firewall",
        "development_protocol_sha256": SHA,
        "gallery_identity_sha256": f"{ordinal % 16:x}" * 64,
        "gallery_requested_size": "5",
        "enrollment_policy_sha256": selection.enrollment_policy["sha256"],
        "case_id": f"case_{pipeline_id}_{ordinal:04d}",
        "anonymous_speaker_id": f"anon_{ordinal:04d}",
        "observation_id": f"obs_{pipeline_id}_{ordinal:04d}",
        "split": "development",
        "truth_state": "UNKNOWN",
        "calibration_role": "calibration",
        "status": "VALID",
        "overlay_condition": "ALL_UNKNOWN",
        "evaluation_material_inspected": False,
        "gallery_size": 5,
        "source_time_sec": 5.0,
        "evidence_duration_sec": 3.0,
        "embedding_consistency": 0.8,
        "top1_score": 0.2 + ordinal / 1000.0,
        "top1_candidate_id": "ENROLLED_0001",
        "top2_score": 0.1,
        "candidate_count": 5,
        "predicted_overlap": False,
    }


def _registry() -> dict[str, object]:
    pipelines = challenger_pipeline_ids()
    observations = [
        _observation(pipeline_id, ordinal + index * 1000)
        for index, pipeline_id in enumerate(pipelines)
        for ordinal in range(1, 6)
    ]
    return build_development_policy_registry(
        observations,
        protocol_id="full_speech_pipeline_v1_synthetic_firewall",
        development_identity_sha256=SHA,
        expected_pipeline_ids=pipelines,
    )


def _artifact(root: Path) -> dict[str, object]:
    checksums = root / "checksums.json"
    return {
        "path": str(root),
        "checksums_path": str(checksums),
        "checksums_sha256": sha256_file(checksums),
        "pipeline_count": 18,
        "sha256": sha256_file(checksums),
    }


def _resign_config_and_checksums(
    root: Path, pipeline_id: str, value: dict[str, object]
) -> None:
    unsigned = dict(value)
    unsigned.pop("freeze_identity_sha256", None)
    value["freeze_identity_sha256"] = sha256_bytes(canonical_json_bytes(unsigned))
    (root / f"{pipeline_id}.yaml").write_text(
        yaml.safe_dump(value, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )
    write_json_atomic(
        root / "checksums.json",
        {
            "schema_version": "full-pipeline-development-config-checksums.v1",
            "pipeline_count": 18,
            "entries": checksum_map(root, exclude=("checksums.json",)),
        },
    )


def test_all18_freeze_matches_live_execution_and_semantic_tamper_fails(
    tmp_path: Path,
) -> None:
    registry = _registry()
    pristine = tmp_path / "pristine"
    freeze_all_pipeline_configs(
        policy_registry=registry,
        protocol_id="full_speech_pipeline_v1_synthetic_firewall",
        development_protocol_sha256=SHA,
        development_result_set_sha256="b" * 64,
        output_root=pristine,
        runtime_anchor_qualification=ANCHOR_QUALIFICATION,
    )

    validation = _validate_frozen_configs(_artifact(pristine), policy_registry=registry)
    assert validation["pipeline_count"] == 18
    assert validation["execution_contract_validation"] == "EXACT_LIVE_MATCH"

    pipeline_id = "fullpipe_v1_ao_dr_ir"
    code_tamper = tmp_path / "code_tamper"
    shutil.copytree(pristine, code_tamper)
    value = yaml.safe_load(
        (code_tamper / f"{pipeline_id}.yaml").read_text(encoding="utf-8")
    )
    files = value["result_affecting_code"]["files"]
    first_path = sorted(files)[0]
    files[first_path] = "f" * 64
    value["result_affecting_code"]["sha256"] = sha256_bytes(canonical_json_bytes(files))
    _resign_config_and_checksums(code_tamper, pipeline_id, value)
    with pytest.raises(CoreEvaluationError, match="result_affecting_code"):
        _validate_frozen_configs(_artifact(code_tamper), policy_registry=registry)

    alignment_tamper = tmp_path / "alignment_tamper"
    shutil.copytree(pristine, alignment_tamper)
    value = yaml.safe_load(
        (alignment_tamper / f"{pipeline_id}.yaml").read_text(encoding="utf-8")
    )
    alignment = value["transcript_alignment_and_buffering"]
    alignment["audio_frame_duration_ms"] = 101
    alignment_core = {
        key: item for key, item in alignment.items() if key != "identity_sha256"
    }
    alignment["identity_sha256"] = sha256_bytes(canonical_json_bytes(alignment_core))
    _resign_config_and_checksums(alignment_tamper, pipeline_id, value)
    with pytest.raises(CoreEvaluationError, match="transcript_alignment_and_buffering"):
        _validate_frozen_configs(_artifact(alignment_tamper), policy_registry=registry)
