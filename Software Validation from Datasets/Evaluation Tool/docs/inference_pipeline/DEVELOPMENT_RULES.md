# Inference Pipeline Development Rules

These rules protect the existing Evaluation Tool while the inference pipeline is
built in small milestones.

## Explicit Interface Rule

All model work must pass through explicit interfaces. Future model code must be
called by the Evaluation Tool through a named runner or interface, with typed or
documented inputs and outputs. Hidden side effects, direct scorer writes, direct
dataset loader edits, and implicit file contracts are not acceptable.

## Protected Evaluation Tool Boundaries

Future model code must not directly modify these areas:

- dataset registry: `app/dataset_registry/`
- scorer: `app/scoring/`
- plotting: `app/plotting/`
- reporting: `app/reporting/`
- GUI: `app/gui/`
- CLI: `app/cli/`
- normalized metadata loading: `app/dataset_registry/loader.py`
- normalized metadata tables: `../Normalized Metadata/`

Changes to these areas require an explicit milestone reason, focused tests, and
a milestone report that explains the behavioral impact.

## Runner Contract Rules

- The model must use `record["inference_audio_path"]` as the audio source.
- `record["inference_audio_path"]` may point to original audio or a temporary
  augmented WAV.
- Predictions must preserve `recording_id` exactly.
- Predictions must preserve `utt_id` exactly because scoring matches on
  `(recording_id, utt_id)`.
- `start_sec` and `end_sec` must be preserved when present.
- `speaker_label` must be preserved when present, or written as null when
  unavailable.
- Predictions must be written to `predictions/utterances.jsonl`.
- Each utterance prediction row must contain `recording_id`, `utt_id`,
  `start_sec`, `end_sec`, `speaker_label`, and `text`.

## Milestone Completion Rules

Each milestone must produce:

- tests or smoke checks appropriate to the risk of the change
- a short markdown report under `reports/milestones/`
- an updated row in `docs/inference_pipeline/MILESTONE_LEDGER.md`

A milestone is not complete until its tests or smoke checks have been run, the
report has been written, and open issues have been recorded.

## Scope Control

- Keep each milestone small enough for one person to review and test.
- Do not add model code unless the active milestone explicitly requires it.
- Do not refactor evaluator behavior as part of model integration work.
- Prefer PyTorch-native model modules in future implementation milestones so
  Raspberry Pi, ExecuTorch, and custom hardware optimization remain possible.
- Stop and report blockers if dependencies, model assets, or required contract
  files are unavailable.

