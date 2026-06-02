# End-to-End Pipeline Report

## Report Metadata
- Run id: `20260601_131900_cmu_arctic_full_m13_e2e_smoke`
- Git commit: `61108dd64ee5df3408cb08442d4c21347aa724d3`
- Config path: `runs/20260601_131900_cmu_arctic_full_m13_e2e_smoke/run_config.yaml`
- Date: `2026-06-02T14:25:42+00:00`
- Hardware platform: `macOS-15.5-arm64-arm-64bit-Mach-O`
- Runtime device: `cpu`

## Dataset Selection
```json
{
  "audio_format": "wav",
  "dataset_id": "cmu_arctic",
  "dataset_key": "cmu_arctic",
  "dataset_name": "CMU Arctic",
  "evaluation_unit": "one utterance WAV file",
  "max_recordings": 1,
  "missing_audio_count": 0,
  "normalized_metadata_dir": "Normalized Metadata/CMU_Arctic",
  "records_manifest": "dataset_selection_records.jsonl",
  "reference_tables": {
    "recordings": "Normalized Metadata/CMU_Arctic/recordings.parquet",
    "utterances": "Normalized Metadata/CMU_Arctic/utterances.parquet"
  },
  "rows_after_filters": 15583,
  "selected_accent_counts": {
    "US English": 1
  },
  "selected_accent_group_counts": {
    "native_us": 1
  },
  "selected_evaluation_items": 1,
  "selected_gender_counts": {
    "male": 1
  },
  "selected_recordings": 1,
  "selected_source_recordings": 1,
  "selected_source_records": 1,
  "selected_speaker_variant_group_counts": {
    "additional": 1
  },
  "source_records_manifest": "dataset_selection_source_records.jsonl",
  "subset_filters": {},
  "total_metadata_rows": 15583
}
```

## Configuration Snapshot
```json
{
  "run_config.yaml": {
    "augmentation": {
      "conditions": [
        {
          "condition_id": "clean",
          "mode": "none",
          "noise_type": null,
          "rir_label": null,
          "rir_path": null,
          "snr_db": null
        }
      ],
      "keep_temp_audio": false,
      "mode": "none",
      "peak_limit": 0.98,
      "preview_count": 0,
      "preview_enabled": false,
      "preview_recording_id": null,
      "seed": 1337
    },
    "command": "full",
    "dataset": {
      "dataset_id": "cmu_arctic",
      "key": "cmu_arctic",
      "name": "CMU Arctic",
      "normalized_metadata_dir": "Normalized Metadata/CMU_Arctic"
    },
    "prediction_contract": {
      "minimum_file": "predictions/utterances.jsonl",
      "optional_files": [
        "predictions/words.jsonl",
        "predictions/segments.rttm"
      ]
    },
    "project_root": "../../..",
    "project_root_relative_to_run": "../../..",
    "run_dir": ".",
    "run_name": "m13_e2e_smoke",
    "runner": {
      "name": "external-stub",
      "simulation_mode": null
    },
    "selection": {
      "max_recordings": 1,
      "selected_recordings": 1,
      "selected_source_recordings": 1,
      "subset_filters": {},
      "total_evaluation_duration_sec": 3.880063,
      "total_source_duration_sec": 3.880063
    }
  }
}
```

## Model Versions
```json
{
  "asr": "no_op_asr",
  "runner": "external-stub",
  "speaker_embedding": "no_op_speaker_embedding"
}
```

## Metrics Summary
- Machine-readable summary rows: `81`
- Diagnostics rows: `1`

### Aggregate

```json
{
  "aggregate_wer": 1.0,
  "audio_missing": 0,
  "deletions": 5,
  "duplicate_prediction_rows_ignored": 0,
  "errors": 8,
  "hypothesis_words": 3,
  "insertions": 0,
  "max_recording_wer": 1.0,
  "mean_recording_wer": 1.0,
  "median_recording_wer": 1.0,
  "missing_prediction_count": 0,
  "missing_prediction_rate": 0.0,
  "missing_predictions": 0,
  "prediction_files_present": {
    "segments.rttm": false,
    "utterances.jsonl": true,
    "words.jsonl": false
  },
  "prediction_rows": 1,
  "processed_prediction_count": 1,
  "processed_predictions": 1,
  "reference_words": 8,
  "scored_duration_sec": 3.880063,
  "selected_recording_count": 1,
  "selected_recordings": 1,
  "speaker_label_accuracy": 0.0,
  "speaker_label_matches": 0,
  "speaker_label_scored": 1,
  "substitutions": 3,
  "total_duration_sec": 3.880063,
  "unexpected_prediction_recordings": 0
}
```

### Asr

```json
{
  "aggregate_wer": 1.0,
  "deletions": 5,
  "errors": 8,
  "hypothesis_words": 3,
  "insertions": 0,
  "max_recording_wer": 1.0,
  "mean_recording_wer": 1.0,
  "median_recording_wer": 1.0,
  "missing_prediction_rate": 0.0,
  "prediction_rows": 1,
  "processed_prediction_count": 1,
  "reference_words": 8,
  "selected_recording_count": 1,
  "substitutions": 3,
  "total_duration_sec": 3.880063
}
```

### Speaker

```json
{
  "accepted_count": 0,
  "decision_count": 2,
  "false_known_count": 0,
  "false_known_rate": null,
  "speaker_accuracy": null,
  "speaker_label_accuracy": 0.0,
  "speaker_label_matches": 0,
  "speaker_label_scored": 1,
  "speaker_scored_count": 0,
  "threshold_decision_counts": {
    "disabled": 2
  },
  "unknown_count": 2,
  "unknown_rate": 1.0
}
```

### Runtime

```json
{
  "audio_duration_sec_total": 3.8800625,
  "device": "cpu",
  "realtime_factor_max": 0.0010987258609277786,
  "realtime_factor_mean": 0.0010987258609277786,
  "runtime_row_count": 1,
  "stage_breakdown_sec_mean": {
    "asr_sec": 6.0874997870996594e-05,
    "audio_load_sec": 0.0014027500001247972,
    "postprocess_sec": 0.0001376250002067536,
    "speaker_sec": 0.0001320409937761724,
    "vad_sec": 0.0024329999869223684
  },
  "total_runtime_sec_max": 0.004263125010766089,
  "total_runtime_sec_mean": 0.004263125010766089
}
```

### Runner

```json
{
  "attempted_count": 1,
  "condition_prediction_counts": {
    "clean": 1
  },
  "failed_count": 0,
  "predictions_path": "utterances.jsonl",
  "run_duration_sec": 0.021549582976149395,
  "runner": "external_stub",
  "skipped_count": 0,
  "written_count": 1
}
```

### Artifacts

```json
{
  "has_aggregate_metrics": true,
  "has_per_recording_metrics": true,
  "has_utterance_predictions": true,
  "metrics_file_count": 12,
  "plots_file_count": 11,
  "predictions_file_count": 6,
  "report_file_count": 2
}
```

## Validation Scores
- Report completeness score: `1.0000`
- Reproducibility score: `1.0000`
- Comparison readiness score: `1.0000`
- Required sections missing: `[]`

## Recommendation
Improve enrollment coverage or thresholds; most decisions are Unknown.

## Artifacts
- Source Run Dir: `runs/20260601_131900_cmu_arctic_full_m13_e2e_smoke`
- Markdown: `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.md`
- Csv: `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.csv`
- Json: `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.json`
- Report Index: `reports/report_index.csv`
