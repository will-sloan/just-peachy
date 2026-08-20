from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.hybrid_speaker_attribution.analysis import collect
from app.hybrid_speaker_attribution.contracts import HybridAttributionError, canonical_sha256, load_frozen_config
from app.hybrid_speaker_attribution.embedding_cache import cache_identity, embedding_job
from app.hybrid_speaker_attribution.protocol import prepare_protocol, validate_protocol
from app.hybrid_speaker_attribution.runner import run_tier


TOOL_ROOT = Path(__file__).resolve().parents[2]


def test_protocol_has_exact_overlays_and_no_waveform_copy(tmp_path):
    root = tmp_path / "protocol"
    prepared = prepare_protocol(benchmark_root=TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1", output_root=root)
    validated = validate_protocol(root, benchmark_root=TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1")
    assert prepared["valid"] and validated["valid"]
    assert validated["enrollment_mixture_intersection"] == 0
    assert validated["development_evaluation_speaker_intersection"] == 0
    assert not list(root.rglob("*.wav")) and not list(root.rglob("*.mp3"))


def test_embedding_cache_identity_is_threshold_independent(tmp_path):
    path = tmp_path / "audio with spaces.wav"
    first = embedding_job(job_id="segment", audio_path=path, audio_sha256="A" * 64, start_sec=0, end_sec=1, role="predicted_segment", metadata={"threshold": 0.1})
    second = embedding_job(job_id="segment", audio_path=path, audio_sha256="A" * 64, start_sec=0, end_sec=1, role="predicted_segment", metadata={"threshold": 0.9})
    assert first["job_identity"] == second["job_identity"]
    assert "audio with spaces" in first["audio_path"]
    assert cache_identity(first["job_identity"], "backend", "A" * 64) != cache_identity(first["job_identity"], "backend", "B" * 64)


def test_frozen_configuration_hash_and_evaluation_gate(tmp_path):
    payload = {
        "schema_version": "hybrid-speaker-attribution-frozen-config.v1",
        "development_decision_status": "frozen",
        "evaluation_tuning_prohibited": True,
        "attribution_settings": {"product_threshold": 0.5},
    }
    payload["hybrid_config_sha256"] = canonical_sha256(payload)
    path = tmp_path / "frozen.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_frozen_config(path)["evaluation_tuning_prohibited"] is True
    payload["attribution_settings"]["product_threshold"] = 0.9
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HybridAttributionError, match="hash mismatch"):
        load_frozen_config(path)


def test_collection_excludes_audio_models_and_cache(tmp_path):
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "analysis_manifest.json").write_text(json.dumps({"analysis_id": "a1"}), encoding="utf-8")
    (analysis / "report.md").write_text("ok", encoding="utf-8")
    protocol = tmp_path / "protocol"
    protocol.mkdir()
    (protocol / "protocol_summary.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "collected"
    result = collect(analysis_root=analysis, output_root=output, protocol_root=protocol)
    assert result["contains_audio"] is False
    assert result["contains_model_assets"] is False
    assert not list(output.rglob("*.wav"))


def test_evaluation_refuses_to_start_without_frozen_configuration(tmp_path):
    with pytest.raises(HybridAttributionError, match="frozen-hybrid-config"):
        run_tier(
            tier="evaluation",
            speaker_backend="campplus_speaker_embedding",
            diarization_pipeline="sherpa_onnx_diarization",
            enrollment_policy_path=TOOL_ROOT / "configs" / "automated_evaluation" / "hybrid_enrollment_policy.non_scientific_smoke.yaml",
            diarization_result_root=tmp_path / "diarization",
            result_root=tmp_path / "hybrid",
            benchmark_root=TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1",
            protocol_root=TOOL_ROOT / "benchmarks" / "hybrid_speaker_attribution" / "hybrid_speaker_attribution_v1",
            run_diarization=False,
        )
