from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from app.campaign_executor.runtime import _resolve_and_verify_pipeline
from app.extended_screening.analysis import analyze_extended_screening_campaign
from app.extended_screening.contracts import (
    eligible_backend_rows,
    load_qualification_registry,
    validate_catalog_qualification_alignment,
)
from app.extended_screening.plan import build_extended_screening_plan
from app.extended_screening.smoke import build_real_smoke_matrix
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.resolver import PipelineResolutionError, resolve_pipeline


TOOL_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = TOOL_ROOT.parent
BENCHMARK_ROOT = TOOL_ROOT / "benchmarks" / "v1"
PIPELINE = TOOL_ROOT / "configs" / "inference" / "live_mic_whisper_base.yaml"
ELIGIBLE_IDS = {
    "faster_whisper",
    "sherpa_onnx_asr",
    "vosk",
    "webrtc_vad",
    "sherpa_onnx_vad",
    "resemblyzer",
    "wespeaker",
    "sherpa_onnx_speaker_embedding",
    "sherpa_onnx_diarization",
}


@pytest.fixture(scope="module")
def stage9_plan(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    output = tmp_path_factory.mktemp("stage9-plan")
    return output, build_extended_screening_plan(BENCHMARK_ROOT, output)


@pytest.fixture(scope="module")
def real_smoke(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    return build_real_smoke_matrix(
        output_root=tmp_path_factory.mktemp("stage9-real-smoke"),
        rerun=False,
    )


def test_qualification_registry_selects_only_real_stage8_successes() -> None:
    registry = load_qualification_registry()
    eligible = eligible_backend_rows(registry)

    assert {str(row["backend_id"]) for row in eligible} == ELIGIBLE_IDS
    excluded = {
        str(row["backend_id"]): str(row["status"])
        for row in registry["backends"]
        if row["disposition"] == "exclude"
    }
    assert excluded == {
        "wenet": "unavailable_asset",
        "pyannote_community": "licence_action_required",
        "picovoice_falcon": "licence_action_required",
        "nemo_diarization": "platform_required",
    }


def test_catalog_records_stage8_profile_assets_parameters_and_status() -> None:
    catalog = ComponentCatalog.load()
    registry = load_qualification_registry()
    validate_catalog_qualification_alignment(registry, catalog)
    faster = catalog.get("asr", "faster_whisper")

    assert faster.environment_profiles == ("extended-local",)
    assert faster.qualification_status == "qualified"
    assert faster.qualification_backend_id == "faster_whisper"
    assert "device" in faster.supported_parameters
    assert faster.model_asset_identity[0]["observed_sha256"]
    assert faster.model_asset_identity[0]["present"] is True


def test_resolver_rejects_wrong_or_mixed_extended_environments() -> None:
    with pytest.raises(PipelineResolutionError, match="incompatible"):
        resolve_pipeline(
            PIPELINE,
            component_overrides={"asr": "faster_whisper"},
            environment_profile="onnx",
        )
    with pytest.raises(PipelineResolutionError, match="no common environment"):
        resolve_pipeline(
            PIPELINE,
            component_overrides={
                "asr": "faster_whisper",
                "vad": "sherpa_onnx_vad",
            },
        )


def test_plan_is_targeted_deterministic_and_uses_identical_core_items(
    stage9_plan: tuple[Path, dict[str, object]],
    tmp_path: Path,
) -> None:
    output, first = stage9_plan
    second = build_extended_screening_plan(BENCHMARK_ROOT, tmp_path / "second")

    assert first["plan_hash"] == second["plan_hash"]
    assert first["scenario_catalog"]["sha256"] == second["scenario_catalog"]["sha256"]
    assert first["benchmark"]["item_count"] == 165
    assert first["scenario_catalog"]["scenario_count"] == 228
    assert len(first["candidate_definitions"]) == 19
    stages = {stage["stage_id"]: stage for stage in first["stages"]}
    assert len(stages["B"]["candidates"]) == 6
    assert len(stages["C"]["candidates"]) == 9
    assert len(stages["E"]["candidates"]) == 4
    assert stages["Q"]["candidates"] == ["composition__sherpa_onnx_diarization"]
    assert stages["D"]["candidates"] == []
    item_hashes = {
        row["comparison_item_set_sha256"]
        for row in first["candidate_definitions"].values()
    }
    assert item_hashes == {first["benchmark"]["item_identity_sha256"]}
    assert (output / "extended_component_comparison_tables.json").is_file()
    assert (output / "environment_compatibility_matrix.json").is_file()
    assert (output / "benchmark_coverage_report.json").is_file()
    assert (output / "advancement_and_exclusion_report.json").is_file()
    assert (output / "shortlist_manifest.json").is_file()


def test_every_qualified_backend_is_selectable_in_a_normal_scenario(
    stage9_plan: tuple[Path, dict[str, object]],
) -> None:
    output, plan = stage9_plan
    scenarios = [
        json.loads(line)
        for line in (output / "extended_screening_scenarios.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    selected_backend_ids = {
        backend_id
        for definition in plan["candidate_definitions"].values()
        for backend_id in definition["qualification_backend_ids"]
    }
    assert selected_backend_ids == ELIGIBLE_IDS
    faster_id = next(
        scenario_id
        for scenario_id in next(
            stage for stage in plan["stages"] if stage["stage_id"] == "B"
        )["scenario_ids_by_candidate"]["full_record__faster_whisper"]
    )
    scenario = next(row for row in scenarios if row["scenario_id"] == faster_id)
    resolution = _resolve_and_verify_pipeline(PROJECT_ROOT, scenario)
    assert resolution.pipeline_config.components["asr"].name == "faster_whisper"
    assert resolution.environment_profile == "extended-local"
    assert scenario["pipeline"]["environment_identity"]["package_freeze_sha256"]


def test_targeted_interactions_require_explicit_compatible_shortlists(
    tmp_path: Path,
) -> None:
    result = build_extended_screening_plan(
        BENCHMARK_ROOT,
        tmp_path / "compatible",
        asr_shortlist=["faster_whisper"],
        vad_shortlist=["webrtc_chunks"],
        embedding_shortlist=["resemblyzer"],
    )
    stage = next(value for value in result["stages"] if value["stage_id"] == "D")
    assert set(stage["candidates"]) == {
        "target__webrtc_chunks__faster_whisper",
        "embedding_target__webrtc_chunks__resemblyzer",
    }
    with pytest.raises(PipelineResolutionError, match="incompatible Stage 8 profiles"):
        build_extended_screening_plan(
            BENCHMARK_ROOT,
            tmp_path / "incompatible",
            asr_shortlist=["faster_whisper"],
            vad_shortlist=["sherpa_onnx_chunks"],
        )


def test_analysis_preserves_missing_denominators_and_environment_groups(
    stage9_plan: tuple[Path, dict[str, object]],
    tmp_path: Path,
) -> None:
    plan_root, plan = stage9_plan
    campaign = tmp_path / "campaign"
    (campaign / "analysis").mkdir(parents=True)
    (campaign / "benchmark_manifests").mkdir()
    manifest_name = str(plan["benchmark"]["manifest"]["path"])
    shutil.copy2(
        BENCHMARK_ROOT / manifest_name,
        campaign / "benchmark_manifests" / manifest_name,
    )
    index_path = campaign / "analysis" / "analysis_input_index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema_version": "analysis-input-index.v1",
                "campaign_id": "campaign_stage9_missing",
                "analysis_input_id": "analysis_stage9_missing",
                "scenario_results": [],
            }
        ),
        encoding="utf-8",
    )
    embedding_path = tmp_path / "embedding.jsonl"
    embedding_path.write_text(
        json.dumps(
            {
                "candidate_id": "fixed_segments__speechbrain_ecapa",
                "item_id": "same-item",
                "segment_id": "same-item",
                "condition": "clean",
                "repetition": 1,
                "duration_sec": 1.0,
                "status": "ok",
                "vector": [1.0, 0.0],
                "extraction_sec": 0.1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = analyze_extended_screening_campaign(
        plan_root / "extended_screening_plan.json",
        index_path,
        embedding_results_path=embedding_path,
        output_dir=tmp_path / "analysis-output",
    )

    stage_b = next(stage for stage in result["stages"] if stage["stage_id"] == "B")
    assert stage_b["identical_benchmark_items"] is True
    assert all(row["missing_prediction_rate"] == 1.0 for row in stage_b["candidates"])
    assert all(row["hardware_group_id"] for row in stage_b["candidates"])
    assert stage_b["selection"]["opaque_composite_score_used"] is False
    embedding = result["embedding_screen"]
    assert embedding["identical_source_segments"] is True
    missing = next(
        row
        for row in embedding["candidates"]
        if row["candidate_id"] == "fixed_segments__resemblyzer"
    )
    assert missing["extraction_success_rate"] == 0.0
    assert result["missing_and_failed_outputs_in_denominators"] is True
    assert (tmp_path / "analysis-output" / "shortlist_manifest.json").is_file()


@pytest.mark.parametrize("backend_id", sorted(ELIGIBLE_IDS))
def test_real_screening_smoke_evidence_for_every_qualified_backend(
    real_smoke: dict[str, object],
    backend_id: str,
) -> None:
    rows = {str(row["backend_id"]): row for row in real_smoke["results"]}
    row = rows[backend_id]

    assert row["status"] == "passed"
    assert row["output_contract_valid"] is True
    assert row["repetitions"] >= 2
    assert row["implicit_downloads_allowed"] is False
    assert row["environment_profile"] in {"extended-local", "onnx", "wespeaker"}
    assert row["component_identity"]["config_sha256"]
    if row["catalog_family"] == "diarization":
        assert row["metrics"]["scientific_metrics_emitted"] is False


def test_smoke_matrix_uses_one_item_and_never_claims_full_science(
    real_smoke: dict[str, object],
) -> None:
    assert real_smoke["summary"] == {
        "expected_backends": 9,
        "real_smoke_passed": 9,
        "failed": 0,
        "identical_item_for_every_backend": True,
    }
    assert real_smoke["scientific_screening_complete"] is False
    assert real_smoke["secret_audit"]["values_serialized"] is False
