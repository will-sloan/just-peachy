import importlib
import sys
from pathlib import Path

import pytest

from app.inference_pipeline.config import PipelineConfig


TOOL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = TOOL_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

runner = importlib.import_module("run_realtime_component_sweep")


def compact_sweep() -> dict[str, object]:
    return {
        "models": [
            {
                "id": "base",
                "component_name": "whisper_base",
                "adapter": "WhisperBaseASRAdapter",
                "model_size": "base",
            },
            {
                "id": "small",
                "enabled": False,
                "component_name": "whisper_small",
                "adapter": "WhisperSmallASRAdapter",
                "model_size": "small",
            },
        ],
        "devices": [{"id": "cpu", "device": "cpu", "dtype": "float32"}],
        "window_profiles": [
            {"id": "3s", "window_sec": 3.0, "hop_sec": 3.0},
        ],
        "vad_profiles": [{"id": "none", "kind": "none"}],
        "speaker_thresholds": [0.6, 0.8],
        "scoring_modes": ["centroid"],
        "word_timestamps": [False],
        "beam_sizes": [1],
        "queue_profiles": [
            {"id": "all", "max_queue": 16, "drop_policy": "drop_oldest"},
        ],
    }


def test_build_cases_creates_cartesian_product(tmp_path: Path) -> None:
    cases = runner.build_cases(
        compact_sweep(),
        input_overrides=(tmp_path / "sample.wav",),
        duration_override=4.0,
    )

    assert len(cases) == 2
    assert {case.threshold for case in cases} == {0.6, 0.8}
    assert all(case.model["id"] == "base" for case in cases)


def test_model_filter_can_select_disabled_expanded_model(tmp_path: Path) -> None:
    cases = runner.build_cases(
        compact_sweep(),
        model_filter={"small"},
        input_overrides=(tmp_path / "sample.wav",),
        duration_override=4.0,
    )

    assert len(cases) == 2
    assert all(case.model["model_size"] == "small" for case in cases)


def test_case_config_applies_model_runtime_vad_and_matching(tmp_path: Path) -> None:
    sweep = compact_sweep()
    sweep["vad_profiles"] = [
        {
            "id": "energy",
            "kind": "energy",
            "params": {"threshold": 0.01},
            "segmentation_params": {"min_chunk_sec": 0.2},
        }
    ]
    case = runner.build_cases(
        sweep,
        input_overrides=(tmp_path / "sample.wav",),
        duration_override=4.0,
    )[0]
    base = PipelineConfig.from_yaml_path(
        TOOL_ROOT / "configs" / "inference" / "live_mic_realtime_whisper_base_speaker_matching.yaml"
    )

    config = runner.build_case_config(base, case, allow_model_downloads=False)

    assert config["components"]["asr"]["params"]["model_size"] == "base"
    assert config["components"]["vad"]["name"] == "energy_vad"
    assert config["components"]["segmentation"]["name"] == "vad_chunks"
    assert config["components"]["speaker_matching"]["params"]["threshold"] == pytest.approx(0.6)


def test_summarize_run_extracts_stage_and_speaker_metrics() -> None:
    summary = {
        "prediction_count": 1,
        "dropped_window_count": 0,
        "metrics": {
            "latency_sec": {"mean": 0.5, "max": 0.7},
            "asr_realtime_factor": {"mean": 0.2, "max": 0.3},
        },
        "diagnostics_rows": [
            {
                "diagnostics": {
                    "runtime_stats": {
                        "total_sec": 0.45,
                        "stage_breakdown_sec": {"asr_sec": 0.3, "speaker_sec": 0.1},
                    },
                    "speaker_decisions": [{"accepted": True, "confidence": 0.75}],
                }
            }
        ],
        "worker_errors": [],
    }

    result = runner.summarize_run(summary)

    assert result["pipeline_runtime_mean_sec"] == pytest.approx(0.45)
    assert result["speaker_accepted_count"] == 1
    assert result["speaker_score_mean"] == pytest.approx(0.75)
