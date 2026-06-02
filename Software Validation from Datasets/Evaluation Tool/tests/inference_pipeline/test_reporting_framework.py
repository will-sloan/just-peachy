from __future__ import annotations

import csv
import json
from pathlib import Path

from app.inference_pipeline.reporting import (
    generate_report_from_run,
    template_path_for_component,
)


def test_component_report_generation_from_prior_run_shape(tmp_path: Path) -> None:
    run_dir = synthetic_run_dir(tmp_path)
    reports_root = tmp_path / "reports"

    artifacts = generate_report_from_run(
        run_dir,
        component_type="end-to-end",
        reports_root=reports_root,
        generated_at="2026-06-02T00:00:00+00:00",
        git_commit="abc123",
    )

    assert artifacts.markdown_path.exists()
    assert artifacts.csv_path.exists()
    assert artifacts.json_path.exists()
    assert artifacts.index_path.exists()
    markdown = artifacts.markdown_path.read_text(encoding="utf-8")
    assert "## Report Metadata" in markdown
    assert "## Configuration Snapshot" in markdown
    assert "tiny-test@1" in markdown
    assert "config_name" in markdown

    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["run_id"] == run_dir.name
    assert payload["metadata"]["model_versions"]["asr"] == "tiny-test@1"
    assert payload["validation"]["report_completeness_score"] == 1.0
    assert payload["validation"]["reproducibility_score"] == 1.0
    assert payload["validation"]["comparison_readiness_score"] == 1.0

    with artifacts.csv_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["metric"] for row in rows} >= {
        "aggregate_wer",
        "speaker_label_accuracy",
        "realtime_factor_mean",
    }


def test_report_index_deduplicates_same_report_identity(tmp_path: Path) -> None:
    run_dir = synthetic_run_dir(tmp_path)
    reports_root = tmp_path / "reports"

    first = generate_report_from_run(
        run_dir,
        component_type="asr",
        reports_root=reports_root,
        generated_at="2026-06-02T00:00:00+00:00",
        git_commit="abc123",
    )
    second = generate_report_from_run(
        run_dir,
        component_type="asr",
        reports_root=reports_root,
        generated_at="2026-06-02T00:00:01+00:00",
        git_commit="abc123",
    )

    assert first.index_path == second.index_path
    with second.index_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["component_type"] == "asr"
    assert rows[0]["generated_at"] == "2026-06-02T00:00:01+00:00"


def test_required_report_templates_exist() -> None:
    for component in (
        "asr",
        "vad",
        "segmentation",
        "speaker_embedding",
        "speaker_matching",
        "enrollment",
        "enrollment_prompts",
        "runtime",
        "end_to_end",
    ):
        path = template_path_for_component(component)
        text = path.read_text(encoding="utf-8")
        assert "{{metadata_block}}" in text
        assert "## Metrics Summary" in text


def synthetic_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "runs" / "20260602_synthetic_m14"
    (run_dir / "metrics").mkdir(parents=True)
    (run_dir / "predictions").mkdir(parents=True)
    (run_dir / "plots").mkdir(parents=True)
    (run_dir / "report").mkdir(parents=True)
    (run_dir / "run_config.yaml").write_text(
        """
command: full
config_name: synthetic_m14_reporting
dataset:
  key: cmu_arctic
  name: CMU Arctic
selection:
  max_recordings: 1
  selected_recordings: 1
components:
  asr:
    name: tiny-test
    enabled: true
    adapter: TinyAdapter
    params:
      model_name: tiny-test@1
  speaker_matching:
    name: cosine_threshold
    enabled: true
    adapter: CosineThresholdSpeakerMatcher
    params:
      model_name: speaker-match-test@1
runner:
  name: external-stub
""",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "dataset_selection.json",
        {
            "dataset_key": "cmu_arctic",
            "selected_evaluation_items": 1,
            "subset_filters": {},
        },
    )
    (run_dir / "dataset_selection_records.jsonl").write_text(
        json.dumps(
            {
                "recording_id": "rec-001",
                "utt_id": "utt-001",
                "reference_text": "hello world",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "metrics" / "aggregate_metrics.json",
        {
            "aggregate_wer": 0.25,
            "mean_recording_wer": 0.25,
            "missing_prediction_rate": 0.0,
            "prediction_rows": 1,
            "processed_prediction_count": 1,
            "selected_recording_count": 1,
            "speaker_label_accuracy": 1.0,
            "speaker_label_matches": 1,
            "speaker_label_scored": 1,
            "total_duration_sec": 2.0,
        },
    )
    (run_dir / "metrics" / "per_recording_metrics.csv").write_text(
        "recording_id,utt_id,wer,missing_prediction\nrec-001,utt-001,0.25,false\n",
        encoding="utf-8",
    )
    _write_json(
        run_dir / "predictions" / "runner_summary.json",
        {
            "runner": "external_stub",
            "attempted_count": 1,
            "written_count": 1,
            "failed_count": 0,
        },
    )
    (run_dir / "predictions" / "diagnostics.jsonl").write_text(
        json.dumps(
            {
                "recording_id": "rec-001",
                "utt_id": "utt-001",
                "diagnostics": {
                    "runtime_stats": {
                        "total_sec": 0.5,
                        "audio_duration_sec": 2.0,
                        "realtime_factor": 0.25,
                        "device": "cpu",
                        "model_versions": {
                            "asr": "tiny-test@1",
                            "speaker_embedding": "embed-test@1",
                        },
                        "stage_breakdown_sec": {
                            "audio_load_sec": 0.1,
                            "asr_sec": 0.2,
                            "speaker_sec": 0.1,
                            "postprocess_sec": 0.1,
                        },
                    },
                    "speaker_decisions": [
                        {
                            "speaker_label": "Alice",
                            "accepted": True,
                            "threshold_decision": "accepted",
                        }
                    ],
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return run_dir


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
