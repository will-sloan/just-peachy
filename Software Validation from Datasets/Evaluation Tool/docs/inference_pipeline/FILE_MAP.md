# Inference Pipeline File Map

M0 records the current Evaluation Tool boundaries and the proposed future
inference-pipeline area. Proposed paths are placeholders only; they are not
implemented in M0.

## Existing Evaluation Tool Paths

### Inference Runner

- `app/model_runner/base.py` - defines `ModelRunner.run_batch`,
  `ModelRunner.predict_one`, `RunnerResult`, and `prediction_from_record`.
- `app/model_runner/external_stub.py` - current external inference integration
  point. Read only in M0.
- `app/model_runner/simulated.py` - built-in fake runner for evaluator
  self-tests and simulation runs.
- `prompts/external_runner_prompt.md` - existing handoff prompt for external
  runner integration.

### Prediction IO

- `app/prediction_io/schema.py` - standardized prediction dataclasses and
  required fields. Read only in M0.
- `app/prediction_io/jsonl.py` - readers and writers for standardized JSONL
  prediction files.
- `app/prediction_io/rttm.py` - optional RTTM prediction support.
- `runs/<run_id>/predictions/utterances.jsonl` - required run output file.
- `runs/<run_id>/predictions/<condition>/utterances.jsonl` - condition-specific
  prediction outputs written by `ModelRunner.run_batch`.
- `runs/<run_id>/predictions/runner_summary.json` - runner summary artifact.

### Dataset Selection and Normalized Metadata

- `app/dataset_registry/registry.py` - supported dataset definitions, aliases,
  subset filters, evaluation modes, and group metric columns.
- `app/dataset_registry/loader.py` - normalized metadata loading and selection.
- `../Normalized Metadata/<dataset>/*.parquet` - normalized dataset tables used
  by the evaluator.
- `../Normalized Metadata/<dataset>/*_preview.csv` - preview tables for
  inspecting normalized metadata.
- `runs/<run_id>/dataset_selection.json` - selection summary for a run.
- `runs/<run_id>/dataset_selection_records.jsonl` - selected evaluation rows.
- `runs/<run_id>/dataset_selection_source_records.jsonl` - selected source rows
  before runtime augmentation expansion.

### Augmentation

- `app/augmentation/config.py` - augmentation configuration models.
- `app/augmentation/processor.py` - runtime augmentation planning,
  materialization, and cleanup.
- `app/augmentation/audio.py` - audio processing helpers.
- `runs/<run_id>/augmentation_config.json` - augmentation settings captured for
  a run.
- `record["inference_audio_path"]` - audio path the model must read. It may be
  original audio or a temporary augmented WAV.

### Scoring

- `app/scoring/scorer.py` - scoring orchestration against predictions and
  selected metadata rows.
- `app/scoring/text.py` - text normalization helpers for scoring.
- `app/scoring/wer.py` - WER utilities.
- `runs/<run_id>/metrics/aggregate_metrics.json` - aggregate score output.
- `runs/<run_id>/metrics/per_recording_metrics.csv` - per-recording score
  output.

### Plotting and Reporting

- `app/plotting/plots.py` - plot generation.
- `app/reporting/reporter.py` - markdown and JSON report generation.
- `runs/<run_id>/plots/*.png` - generated plots.
- `runs/<run_id>/report/report.md` - generated run report.
- `runs/<run_id>/report/summary.json` - generated report summary.

### CLI and GUI

- `run_evaluation.py` - launcher for the Evaluation Tool CLI.
- `app/cli/main.py` - command definitions for list, GUI, run, score, report,
  and full workflows.
- `app/gui/main.py` - GUI launch flow.
- `app/gui/state.py` - GUI state and command serialization.
- `app/gui/widgets.py` - GUI widgets.
- `app/gui/preview.py` - GUI preview helpers.
- `app/gui/validation_harness.py` - GUI validation and smoke harness.

### Run Folders and Utilities

- `app/utils/run_artifacts.py` - run folder and artifact helpers.
- `app/utils/paths.py` - project and tool path helpers.
- `app/utils/json_utils.py` - JSON and JSONL helpers.
- `app/utils/logging_utils.py` - run logging helpers.
- `runs/<run_id>/run_config.yaml` - run configuration.
- `runs/<run_id>/logs/evaluation.log` - run log.

## Proposed Future Inference-Pipeline Paths

These paths are proposed only. They must not be created or implemented until a
future milestone explicitly requires them.

- `app/inference_pipeline/__init__.py` - proposed package marker.
- `app/inference_pipeline/interfaces.py` - proposed explicit interfaces between
  Evaluation Tool runner code and model code.
- `app/inference_pipeline/audio_io.py` - proposed audio loading and validation
  helpers.
- `app/inference_pipeline/transcription.py` - proposed ASR transcription module.
- `app/inference_pipeline/speaker_labels.py` - proposed speaker label handling.
- `app/inference_pipeline/pytorch_modules/` - proposed PyTorch-native model
  modules that can later be optimized for Raspberry Pi, ExecuTorch, or custom
  hardware.
- `tests/test_inference_pipeline_contract.py` - proposed future contract tests.
- `reports/milestones/M<N>_<milestone_name>_report.md` - proposed future
  milestone report pattern.

## Do Not Change Without Explicit Milestone Reason

Future inference-pipeline work must not change these areas unless a milestone
explicitly names the reason and tests the impact:

- dataset registry: `app/dataset_registry/`
- scorer: `app/scoring/`
- plotting: `app/plotting/`
- reporting: `app/reporting/`
- GUI: `app/gui/`
- CLI: `app/cli/`
- normalized metadata loaders: `app/dataset_registry/loader.py`
- normalized metadata tables: `../Normalized Metadata/`

## Copyable External Runner Contract

```text
The Evaluation Tool calls a ModelRunner with selected metadata rows.

Current integration point:
- app/model_runner/external_stub.py
- ExternalStubRunner.predict_one(record, run_config, logger)

Call shape:
- ModelRunner.run_batch(records, predictions_dir, run_config, logger) receives
  the selected records for a run.
- It calls before_run(records, predictions_dir, run_config, logger).
- It then calls predict_one(record, run_config, logger) once per selected
  evaluation row.
- Runtime augmentation is materialized before predict_one. During augmented
  runs, record["inference_audio_path"] points to a temporary augmented WAV that
  is valid during that call.

Model input rule:
- The model must read record["inference_audio_path"].
- That path may point to original audio or a temporary augmented WAV.
- Do not substitute audio_path_resolved unless a future interface explicitly
  defines that fallback.

Identity preservation:
- Preserve recording_id exactly.
- Preserve utt_id exactly because scoring matches predictions on
  (recording_id, utt_id).
- Preserve start_sec and end_sec when present.
- Preserve speaker_label when present, or write null when unavailable.

Required output:
- Write predictions/utterances.jsonl.
- Each JSONL row must contain:
  - recording_id
  - utt_id
  - start_sec
  - end_sec
  - speaker_label
  - text

Return contract:
- predict_one returns app.prediction_io.schema.UtterancePrediction or None.
- The standard helper prediction_from_record(record, text) builds an
  UtterancePrediction while carrying recording_id, utt_id, start_sec, end_sec,
  and speaker_label from the selected metadata row.

M0 scope:
- Do not modify app/model_runner/external_stub.py.
- Do not modify app/prediction_io/schema.py.
- Do not add model code.
```

