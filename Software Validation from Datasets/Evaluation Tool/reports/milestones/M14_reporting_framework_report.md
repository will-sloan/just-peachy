# M14 - Metrics and Report Generation Framework

## High-Level Summary

M14 adds a reusable inference-pipeline reporting layer that can generate
Markdown, CSV, and JSON reports from an existing run directory without changing
the Evaluation Tool runner, scorer, GUI, dataset registry, or prediction
contract.

The framework reads prior-run artifacts such as `run_config.yaml`,
`dataset_selection.json`, `metrics/aggregate_metrics.json`,
`predictions/runner_summary.json`, and `predictions/diagnostics.jsonl`. Every
generated report includes a standard metadata block with run id, git commit,
config path, config snapshot, dataset selection, model identifiers, hardware,
and generation date.

## Files Added Or Updated

- `app/inference_pipeline/metrics/__init__.py`
- `app/inference_pipeline/metrics/asr_metrics.py`
- `app/inference_pipeline/metrics/speaker_metrics.py`
- `app/inference_pipeline/metrics/runtime_metrics.py`
- `app/inference_pipeline/reporting/__init__.py`
- `app/inference_pipeline/reporting/component_report.py`
- `app/inference_pipeline/reporting/templates/asr.md`
- `app/inference_pipeline/reporting/templates/vad.md`
- `app/inference_pipeline/reporting/templates/segmentation.md`
- `app/inference_pipeline/reporting/templates/speaker_embedding.md`
- `app/inference_pipeline/reporting/templates/speaker_matching.md`
- `app/inference_pipeline/reporting/templates/enrollment.md`
- `app/inference_pipeline/reporting/templates/enrollment_prompts.md`
- `app/inference_pipeline/reporting/templates/runtime.md`
- `app/inference_pipeline/reporting/templates/end_to_end.md`
- `tests/inference_pipeline/test_reporting_framework.py`
- `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.md`
- `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.csv`
- `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.json`
- `reports/report_index.csv`
- `reports/milestones/M14_reporting_framework_report.md`

## What Changed

- Added `ReportMetadata` with run id, git commit, config path, dataset
  selection, model versions, hardware, date, and config snapshot.
- Added `generate_report_from_run(...)` plus a module CLI for generating a
  component report from a prior run directory.
- Added Markdown, CSV summary, and JSON metric writers.
- Added report templates for ASR, VAD, segmentation, speaker embedding,
  speaker matching, enrollment, enrollment prompts, runtime, and end-to-end
  pipeline reports.
- Added report validation scores for completeness, reproducibility, and
  comparison readiness.
- Added a generated report index at `reports/report_index.csv` with the primary
  recommendation for each generated report.
- Added ASR recommendation helpers plus speaker and runtime metric summaries.

## Runner Contract Preservation

No changes were made to `app/model_runner/external_stub.py` or to the required
prediction contract. The required output remains `predictions/utterances.jsonl`
with `recording_id`, `utt_id`, `start_sec`, `end_sec`, `speaker_label`, and
`text`.

## Tests And Smoke Checks

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_reporting_framework.py
```

Result: `3 passed`.

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_reporting_framework.py tests/inference_pipeline/test_asr_benchmark.py tests/inference_pipeline/test_speaker_matching.py tests/inference_pipeline/test_pipeline_e2e.py
```

Result: `20 passed`.

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests
```

Result: `130 passed, 1 warning`. The warning is the existing Torch JIT
deprecation warning under Python 3.14.

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python -m app.inference_pipeline.reporting.component_report --run-dir runs/20260601_131900_cmu_arctic_full_m13_e2e_smoke --component end-to-end
```

Result:

- Markdown report:
  `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.md`
- CSV summary:
  `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.csv`
- JSON metrics:
  `reports/component_reports/end_to_end/end_to_end_report_20260601_131900_cmu_arctic_full_m13_e2e_smoke.json`
- Report index:
  `reports/report_index.csv`

## Validation Scores From Smoke Report

- Report completeness score: `1.0000`
- Reproducibility score: `1.0000`
- Comparison readiness score: `1.0000`

## Milestone Reports Folder Summary

The M14 milestone report was added under `reports/milestones/`. The reusable
component report generated during smoke testing was added under
`reports/component_reports/end_to_end/`, and `reports/report_index.csv` now
indexes the generated report with its primary recommendation.

## Remaining Incomplete Or Blocked

- No required dependencies or model assets blocked M14.
- The smoke report uses the prior M13 no-op ASR and no-op speaker embedding
  model identifiers because that prior run intentionally avoids production model
  downloads.
- The templates are intentionally generic. Future milestones can specialize
  component wording and add richer per-component visual summaries without
  changing the runner contract.
