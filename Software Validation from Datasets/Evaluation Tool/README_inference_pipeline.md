# Inference Pipeline Notes

This is the entry point for the future speech inference pipeline documentation.
M0 establishes the repository baseline, file map, development rules, milestone
ledger, and validation report before any model implementation is added.

No model implementation exists in M0. Future model work must keep using the
existing Evaluation Tool runner contract and must pass through explicit
interfaces before it is considered for scoring or reporting.

## M0 Documents

- [File map](docs/inference_pipeline/FILE_MAP.md)
- [Development rules](docs/inference_pipeline/DEVELOPMENT_RULES.md)
- [Milestone ledger](docs/inference_pipeline/MILESTONE_LEDGER.md)
- [M0 report](reports/milestones/M0_repository_baseline_report.md)

## Current Integration Point

The existing inference integration point remains:

```text
app/model_runner/external_stub.py
```

The required utterance prediction schema remains:

```text
app/prediction_io/schema.py
predictions/utterances.jsonl
```

