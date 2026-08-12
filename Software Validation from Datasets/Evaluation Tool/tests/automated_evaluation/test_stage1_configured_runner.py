from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest
import soundfile as sf
import yaml

from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.config import COMPONENT_SLOTS, PipelineConfig
from app.inference_pipeline.contracts import PipelineOutput
from app.inference_pipeline.resolver import (
    PipelineResolutionError,
    parse_assignments,
    resolve_pipeline,
)
from app.model_runner.configured import ConfiguredEvaluatorRunner
from app.prediction_io.jsonl import read_utterance_predictions
from app.utils.json_utils import read_json, read_jsonl
from app.utils.paths import find_project_root


LOGGER = logging.getLogger(__name__)
TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
REAL_AUDIO = (
    REPOSITORY_ROOT
    / "Software Validation from Datasets"
    / "Raw Datasets (Not formatted)"
    / "CMU Arctic"
    / "cmu_us_aew_arctic"
    / "wav"
    / "arctic_b0476.wav"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _record(audio_path: Path, *, suffix: str = "1") -> dict[str, object]:
    duration = float(sf.info(audio_path).duration)
    return {
        "recording_id": f"recording-{suffix}",
        "source_recording_id": f"source-{suffix}",
        "utt_id": f"utterance-{suffix}",
        "inference_audio_path": str(audio_path),
        "audio_path_resolved": str(audio_path),
        "start_sec": 0.0,
        "end_sec": duration,
        "duration_sec": duration,
        "sample_rate_hz": int(sf.info(audio_path).samplerate),
        "channel_count": int(sf.info(audio_path).channels),
        "channel_index": 0,
        "stream_id": "Array1-01",
        "stream_type": "array",
        "microphone_id": "Array1-01",
        "reference_text": "this reference must never be used as fallback",
        "speaker_label": "reference-speaker-must-not-be-copied",
        "recording_speaker_id_ref": "reference-speaker-id-must-not-be-copied",
        "augmentation_condition_id": "clean",
        "augmentation_mode": "none",
    }


def _run_config(run_dir: Path) -> dict[str, object]:
    return {
        "project_root": str(REPOSITORY_ROOT),
        "run_dir": str(run_dir),
        "runner": {"name": "configured"},
        "augmentation": {
            "mode": "none",
            "conditions": [{"condition_id": "clean", "mode": "none"}],
        },
    }


class StaticPipeline:
    def __init__(
        self,
        *,
        speaker_label: str | None = None,
        text: str | None = "model text",
        diagnostics: dict[str, object] | None = None,
    ):
        self.speaker_label = speaker_label
        self.text = text
        self.diagnostics = diagnostics or {"component": "static"}

    def predict(self, record, config):
        _ = config
        return PipelineOutput(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            start_sec=record.get("start_sec"),
            end_sec=record.get("end_sec"),
            speaker_label=self.speaker_label,
            text=self.text,  # type: ignore[arg-type]
            diagnostics=self.diagnostics,
        )


def test_runner_publishes_typed_streaming_diagnostics(tmp_path: Path) -> None:
    resolution = resolve_pipeline(CONFIG_ROOT / "live_mic_whisper_tiny.yaml")
    run_dir = tmp_path / "run"
    record = _record(REAL_AUDIO)
    runner = ConfiguredEvaluatorRunner(
        resolution,
        pipeline_runner=StaticPipeline(
            diagnostics={
                "streaming": {
                    "schema_version": "streaming-diagnostics.v1",
                    "backend_id": "test",
                    "metrics": {"streaming_rtf": 0.5},
                }
            }
        ),
    )
    config = _run_config(run_dir)
    config["scenario_id"] = "scenario_0123456789ab"

    runner.run_batch([record], run_dir / "predictions", config, LOGGER)
    rows = list(read_jsonl(run_dir / "predictions" / "streaming_diagnostics.jsonl"))

    assert rows[0]["schema_version"] == "streaming-diagnostics-row.v1"
    assert rows[0]["scenario_id"] == "scenario_0123456789ab"
    assert rows[0]["recording_id"] == record["recording_id"]
    assert rows[0]["streaming"]["metrics"]["streaming_rtf"] == 0.5


def test_catalog_discovers_every_runtime_family_and_verifies_sources() -> None:
    catalog = ComponentCatalog.load()

    assert len(catalog.entries) >= 27
    assert {entry.family for entry in catalog.entries} == set(COMPONENT_SLOTS)
    whisper_base = catalog.get("asr", "whisper_base")
    assert whisper_base.implementation_class == "WhisperASR"
    assert whisper_base.source_config_path == "configs/inference/components/asr/whisper_base.yaml"
    assert whisper_base.source_config_sha256 == _sha256(
        TOOL_ROOT / whisper_base.source_config_path
    )
    assert whisper_base.qualification_status == "qualified"
    assert whisper_base.model_identity["model_size"] == "base"
    assert whisper_base.model_asset_identity[0]["hash_matches"] is True
    assert whisper_base.model_asset_identity[0]["present"] is True
    assert catalog.get("asr", "moonshine_streaming_tiny").output_contract == (
        "asr_transcript.v1"
    )
    assert catalog.get("vad", "fsmn_vad").environment_profiles == ("edge-cpu",)


def test_project_root_discovery_accepts_the_repository_raw_dataset_alias() -> None:
    project_root = REPOSITORY_ROOT / "Software Validation from Datasets"

    assert find_project_root(TOOL_ROOT) == project_root


def test_resolver_composes_fragments_and_records_source_and_final_overrides() -> None:
    selected = CONFIG_ROOT / "live_mic_whisper_tiny.yaml"
    source_hash = _sha256(selected)

    resolution = resolve_pipeline(
        selected,
        component_overrides={"asr": "whisper_base"},
        setting_overrides={
            "runtime.num_threads": 2,
            "components.asr.params.beam_size": 3,
        },
    )

    assert _sha256(selected) == source_hash
    assert resolution.pipeline_config.components["asr"].name == "whisper_base"
    assert resolution.pipeline_config.components["asr"].params["beam_size"] == 3
    assert resolution.pipeline_config.runtime.num_threads == 2
    assert resolution.component_sources["asr"]["source_path"] == (
        "configs/inference/components/asr/whisper_base.yaml"
    )
    history = {item.path: item for item in resolution.override_history}
    assert history["components.asr.name"].source_value == "whisper_tiny"
    assert history["components.asr.name"].final_value == "whisper_base"
    assert history["components.asr.params.beam_size"].source_value == 1
    assert history["components.asr.params.beam_size"].final_value == 3
    assert history["runtime.num_threads"].source_value == 1
    assert history["runtime.num_threads"].final_value == 2


def test_resolved_config_is_loadable_and_artifacts_include_identities(tmp_path: Path) -> None:
    resolution = resolve_pipeline(CONFIG_ROOT / "live_mic_whisper_base.yaml")

    paths = resolution.write_artifacts(tmp_path / "inference")
    reloaded = PipelineConfig.from_yaml_path(paths["resolved_inference_config"])
    identities = read_json(paths["component_identity_summary"])
    selected = read_json(paths["selected_inference_config"])

    assert reloaded.components["asr"].name == "whisper_base"
    assert identities["components"]["asr"]["model_identity"]["model_size"] == "base"
    assert identities["components"]["asr"]["source"]["source_sha256"]
    assert selected["selected_inference_config"]["sha256"] == _sha256(
        CONFIG_ROOT / "live_mic_whisper_base.yaml"
    )


@pytest.mark.parametrize("dtype", ["float32", "float16"])
def test_cuda_whisper_base_config_resolves_explicit_device_dtype_and_profile(
    dtype: str,
) -> None:
    resolution = resolve_pipeline(CONFIG_ROOT / f"whisper_base_cuda_{dtype}.yaml")

    assert resolution.environment_profile == "core-cuda"
    assert resolution.pipeline_config.runtime.device == "cuda:0"
    assert resolution.pipeline_config.runtime.precision == dtype
    params = resolution.pipeline_config.components["asr"].params
    assert params["device"] == "cuda:0"
    assert params["dtype"] == dtype
    assert params["allow_model_downloads"] is False


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"runtime.device": "cpu"}, "requires a CUDA runtime device"),
        ({"runtime.precision": "float16"}, "component dtype"),
    ],
)
def test_resolver_prohibits_cuda_device_or_dtype_fallback(
    override: dict[str, object], message: str
) -> None:
    with pytest.raises(PipelineResolutionError, match=message):
        resolve_pipeline(
            CONFIG_ROOT / "whisper_base_cuda_float32.yaml",
            setting_overrides=override,
        )


def test_resolver_rejects_cpu_environment_for_cuda_runtime() -> None:
    with pytest.raises(PipelineResolutionError, match="core-cpu"):
        resolve_pipeline(
            CONFIG_ROOT / "whisper_base_cuda_float32.yaml",
            environment_profile="core-cpu",
        )


def test_resolver_accepts_only_catalog_declared_backend_compute_type() -> None:
    resolution = resolve_pipeline(
        CONFIG_ROOT / "live_mic_whisper_base.yaml",
        component_overrides={"asr": "faster_whisper"},
        environment_profile="extended-local",
    )

    params = resolution.pipeline_config.components["asr"].params
    assert resolution.pipeline_config.runtime.precision == "float32"
    assert params["compute_type"] == "int8"
    assert resolution.environment_profile == "extended-local"


@pytest.mark.parametrize(
    ("component_overrides", "setting_overrides", "message"),
    [
        ({"segmentation": "vad_chunks"}, {}, "requires an active VAD"),
        ({"speaker_matching": "cosine_threshold"}, {}, "requires an active speaker embedding"),
        ({}, {"runtime.allow_model_downloads": True}, "must remain false"),
        (
            {},
            {"components.asr.params.allow_model_downloads": True},
            "must remain false",
        ),
        ({}, {"runtime.not_a_real_field": 1}, "supported runtime field"),
    ],
)
def test_resolver_rejects_incompatible_or_download_enabled_configs(
    component_overrides: dict[str, str],
    setting_overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(PipelineResolutionError, match=message):
        resolve_pipeline(
            CONFIG_ROOT / "live_mic_whisper_tiny.yaml",
            component_overrides=component_overrides,
            setting_overrides=setting_overrides,
        )


def test_resolver_rejects_future_only_profile() -> None:
    with pytest.raises(PipelineResolutionError, match="future-only"):
        resolve_pipeline(CONFIG_ROOT / "raspberry_pi_future.yaml")


def test_assignment_parser_rejects_duplicates_and_preserves_scalar_types() -> None:
    assert parse_assignments(
        ["runtime.num_threads=2", "components.asr.enabled=false"],
        label="override",
    ) == {"runtime.num_threads": 2, "components.asr.enabled": False}
    with pytest.raises(PipelineResolutionError, match="duplicate"):
        parse_assignments(["asr=one", "asr=two"], label="component")


def test_runner_preserves_identity_normalizes_unknown_and_never_uses_reference_fallback(
    tmp_path: Path,
) -> None:
    resolution = resolve_pipeline(CONFIG_ROOT / "live_mic_whisper_tiny.yaml")
    run_dir = tmp_path / "run"
    record = _record(REAL_AUDIO)
    runner = ConfiguredEvaluatorRunner(
        resolution,
        pipeline_runner=StaticPipeline(speaker_label="<unknown>", text=None),
    )

    result = runner.run_batch([record], run_dir / "predictions", _run_config(run_dir), LOGGER)
    predictions = read_utterance_predictions(run_dir / "predictions" / "utterances.jsonl")
    diagnostics = list(read_jsonl(run_dir / "predictions" / "diagnostics.jsonl"))
    failures = list(read_jsonl(run_dir / "predictions" / "failures.jsonl"))

    assert result.written_count == 1
    assert result.failed_count == 0
    assert predictions == [
        {
            "recording_id": record["recording_id"],
            "utt_id": record["utt_id"],
            "start_sec": record["start_sec"],
            "end_sec": record["end_sec"],
            "speaker_label": "Unknown",
            "text": "",
        }
    ]
    assert predictions[0]["text"] != record["reference_text"]
    assert predictions[0]["speaker_label"] != record["speaker_label"]
    assert diagnostics[0]["speaker_label_normalization"] == {
        "original": "<unknown>",
        "normalized": "Unknown",
    }
    assert diagnostics[0]["provenance"]["source_recording_id"] == "source-1"
    assert diagnostics[0]["provenance"]["channel_index"] == 0
    assert diagnostics[0]["provenance"]["stream_id"] == "Array1-01"
    assert "recording_speaker_id_ref" not in diagnostics[0]["provenance"]
    assert record["reference_text"] not in str(diagnostics[0])
    assert record["speaker_label"] not in str(diagnostics[0])
    assert record["recording_speaker_id_ref"] not in str(diagnostics[0])
    assert failures == []
    assert (run_dir / "inference" / "resolved_inference_config.yaml").is_file()
    assert (run_dir / "inference" / "component_identity_summary.json").is_file()


class MixedFailurePipeline:
    def predict(self, record, config):
        _ = config
        if record["utt_id"] == "utterance-1":
            raise FileNotFoundError(f"model asset missing below {REPOSITORY_ROOT}")
        return PipelineOutput(
            recording_id=str(record["recording_id"]),
            utt_id=str(record["utt_id"]),
            start_sec=record.get("start_sec"),
            end_sec=record.get("end_sec"),
            speaker_label="Unknown",
            text="second item succeeds",
        )


def test_runner_isolates_item_failures_and_reports_missing_assets_as_unavailable(
    tmp_path: Path,
) -> None:
    resolution = resolve_pipeline(CONFIG_ROOT / "live_mic_whisper_tiny.yaml")
    run_dir = tmp_path / "run"
    records = [_record(REAL_AUDIO, suffix="1"), _record(REAL_AUDIO, suffix="2")]
    runner = ConfiguredEvaluatorRunner(
        resolution,
        pipeline_runner=MixedFailurePipeline(),
    )

    result = runner.run_batch(records, run_dir / "predictions", _run_config(run_dir), LOGGER)
    predictions = read_utterance_predictions(run_dir / "predictions" / "utterances.jsonl")
    failures = list(read_jsonl(run_dir / "predictions" / "failures.jsonl"))

    assert result.attempted_count == 2
    assert result.written_count == 1
    assert result.failed_count == 1
    assert predictions[0]["utt_id"] == "utterance-2"
    assert failures[0]["utt_id"] == "utterance-1"
    assert failures[0]["status"] == "unavailable"
    assert failures[0]["prerequisite_status"] == "asset_required"
    assert "<project_root>" in failures[0]["message"]
    assert str(REPOSITORY_ROOT) not in failures[0]["message"]


@pytest.mark.parametrize(
    "pipeline",
    [
        object(),
        StaticPipeline(),
    ],
)
def test_malformed_pipeline_or_output_does_not_create_prediction(
    tmp_path: Path,
    pipeline: object,
) -> None:
    if isinstance(pipeline, StaticPipeline):
        pipeline.predict = lambda record, config: {"text": "not PipelineOutput"}  # type: ignore[method-assign]
    resolution = resolve_pipeline(CONFIG_ROOT / "live_mic_whisper_tiny.yaml")
    run_dir = tmp_path / "run"
    runner = ConfiguredEvaluatorRunner(resolution, pipeline_runner=pipeline)

    result = runner.run_batch(
        [_record(REAL_AUDIO)],
        run_dir / "predictions",
        _run_config(run_dir),
        LOGGER,
    )

    assert result.written_count == 0
    assert result.failed_count == 1
    assert read_utterance_predictions(run_dir / "predictions" / "utterances.jsonl") == []
    assert len(list(read_jsonl(run_dir / "predictions" / "failures.jsonl"))) == 1


@pytest.mark.parametrize("field", ["recording_id", "utt_id", "start_sec", "end_sec"])
def test_runner_rejects_changed_identity_or_timestamps(tmp_path: Path, field: str) -> None:
    class ChangedPipeline:
        def predict(self, record, config):
            _ = config
            values = {
                "recording_id": record["recording_id"],
                "utt_id": record["utt_id"],
                "start_sec": record["start_sec"],
                "end_sec": record["end_sec"],
            }
            values[field] = "changed" if field.endswith("id") else 99.0
            return PipelineOutput(
                **values,
                speaker_label=None,
                text="model text",
            )

    resolution = resolve_pipeline(CONFIG_ROOT / "live_mic_whisper_tiny.yaml")
    run_dir = tmp_path / field
    result = ConfiguredEvaluatorRunner(
        resolution,
        pipeline_runner=ChangedPipeline(),
    ).run_batch([_record(REAL_AUDIO)], run_dir / "predictions", _run_config(run_dir), LOGGER)

    assert result.written_count == 0
    assert result.failed_count == 1


@pytest.mark.parametrize(
    ("config_name", "model_file"),
    [
        ("live_mic_whisper_tiny.yaml", "tiny.pt"),
        ("live_mic_whisper_base.yaml", "base.pt"),
    ],
)
def test_real_one_item_whisper_configured_runner_smoke_when_available(
    tmp_path: Path,
    config_name: str,
    model_file: str,
) -> None:
    pytest.importorskip("whisper")
    model_path = REPOSITORY_ROOT / "models" / "cache" / "whisper" / model_file
    if not REAL_AUDIO.is_file() or not model_path.is_file():
        pytest.skip("real speech audio or local Whisper asset is unavailable")
    resolution = resolve_pipeline(CONFIG_ROOT / config_name)
    run_dir = tmp_path / model_file.replace(".pt", "")
    record = _record(REAL_AUDIO)

    result = ConfiguredEvaluatorRunner(resolution).run_batch(
        [record],
        run_dir / "predictions",
        _run_config(run_dir),
        LOGGER,
    )
    predictions = read_utterance_predictions(run_dir / "predictions" / "utterances.jsonl")

    assert result.written_count == 1
    assert result.failed_count == 0
    assert predictions[0]["recording_id"] == record["recording_id"]
    assert predictions[0]["utt_id"] == record["utt_id"]
    assert predictions[0]["start_sec"] == record["start_sec"]
    assert predictions[0]["end_sec"] == record["end_sec"]
    assert isinstance(predictions[0]["text"], str) and predictions[0]["text"]
    resolved = yaml.safe_load(
        (run_dir / "inference" / "resolved_inference_config.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert resolved["runtime"]["allow_model_downloads"] is False
