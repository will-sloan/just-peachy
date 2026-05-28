from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.experiments.enrollment_prompt_eval import (
    DEFAULT_PROMPT_SETS_PATH,
    DEFAULT_SYNTHETIC_SAMPLES_PATH,
    EnrollmentPromptSample,
    evaluate_enrollment_prompts,
    load_prompt_eval_config,
    load_prompt_samples,
    load_prompt_sets,
    prompt_comparison_report_path,
    run_enrollment_prompt_eval,
    write_prompt_comparison_report,
)


CONFIG_PATH = TOOL_ROOT / "configs" / "sweeps" / "enrollment_prompts.yaml"


def test_prompt_sets_load_required_strategies() -> None:
    prompt_sets = load_prompt_sets(DEFAULT_PROMPT_SETS_PATH)

    strategies = {prompt_set.strategy for prompt_set in prompt_sets}

    assert len(prompt_sets) >= 4
    assert "short_phrase" in strategies
    assert "balanced_phoneme_sentence" in strategies
    assert "multiple_short_phrases" in strategies
    assert "long_paragraph" in strategies
    assert all(prompt_set.prompts for prompt_set in prompt_sets)
    assert json.dumps([prompt_set.to_jsonable() for prompt_set in prompt_sets])


def test_sample_schema_requires_embedding_or_embedding_path() -> None:
    valid = EnrollmentPromptSample.from_mapping(
        {
            "sample_id": "sample-1",
            "speaker_id": "spk-1",
            "display_name": "Alice",
            "prompt_id": "balanced_sentence_v1",
            "prompt_set_id": "balanced_sentence",
            "recording_condition": "synthetic_clean",
            "embedding_model": "speaker-embedder@synthetic",
            "duration_sec": 6.0,
            "embedding": [1.0, 0.0, 0.0],
        }
    )

    assert valid.normalized_embedding() == pytest.approx((1.0, 0.0, 0.0))

    invalid = valid.to_jsonable()
    invalid.pop("embedding")
    invalid.pop("embedding_path")
    with pytest.raises(ContractValidationError):
        EnrollmentPromptSample.from_mapping(invalid)


def test_synthetic_prompt_eval_ranks_balanced_sentence_and_writes_report(
    tmp_path: Path,
) -> None:
    prompt_sets = load_prompt_sets(DEFAULT_PROMPT_SETS_PATH)
    samples = load_prompt_samples(DEFAULT_SYNTHETIC_SAMPLES_PATH)
    config = load_prompt_eval_config(CONFIG_PATH)
    matcher = config["matcher"]

    result = evaluate_enrollment_prompts(
        run_id="unit",
        prompt_sets=prompt_sets,
        samples=samples,
        thresholds=tuple(float(value) for value in matcher["thresholds"]),
        min_margin=float(matcher["min_margin"]),
        scoring_mode=str(matcher["scoring_mode"]),
        unknown_label=str(matcher["unknown_label"]),
        conservative_max_false_known_rate=float(matcher["conservative_max_false_known_rate"]),
        fixed_far_targets=tuple(float(value) for value in matcher["fixed_far_targets"]),
        assumptions=["unit synthetic fixtures"],
        incomplete=["real participant recordings not used"],
    )
    report_path = prompt_comparison_report_path(tmp_path / "reports", "unit")
    write_prompt_comparison_report(
        report_path,
        result,
        prompt_sets=prompt_sets,
        samples=samples,
        files_changed=["tests/inference_pipeline/test_enrollment_prompt_eval.py"],
        test_commands=["python -m pytest tests/inference_pipeline/test_enrollment_prompt_eval.py"],
        smoke_commands=[],
        runner_contract="Unit test does not touch the runner contract.",
    )

    assert result.recommended_prompt_set_id == "multiple_short_phrases"
    assert result.recommended_min_duration_sec == pytest.approx(8.0)
    assert len(result.metrics) >= 3
    assert result.metrics[0].false_known_rate == pytest.approx(0.0)
    assert result.metrics[0].known_speaker_accuracy == pytest.approx(1.0)
    assert result.metrics[0].equal_error_rate is not None
    assert result.metrics[0].tar_at_far
    assert "Recommended prompt set" in report_path.read_text(encoding="utf-8")


def test_run_enrollment_prompt_eval_loads_config_and_writes_report(tmp_path: Path) -> None:
    report_path = tmp_path / "prompt_comparison_unit.md"

    result, written_report_path = run_enrollment_prompt_eval(
        run_id="unit_script",
        prompt_sets_path=DEFAULT_PROMPT_SETS_PATH,
        samples_jsonl=DEFAULT_SYNTHETIC_SAMPLES_PATH,
        sweep_config_path=CONFIG_PATH,
        report_path=report_path,
    )

    assert written_report_path == report_path
    assert result.recommended_prompt_set_id == "multiple_short_phrases"
    assert report_path.is_file()
    assert "Duration Vs Performance" in report_path.read_text(encoding="utf-8")
