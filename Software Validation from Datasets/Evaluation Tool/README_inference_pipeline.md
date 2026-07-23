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

## Realtime Component Sweep

`scripts/run_realtime_component_sweep.py` generates an explicit Cartesian
matrix from `configs/sweeps/realtime_component_matrix.yaml`. Each case runs in
an isolated subprocess and writes its generated config, console log, original
run summary, and a checkpointed result row. The consolidated outputs are
`results.jsonl` and `results.csv`.

Preview the default matrix without running models:

```powershell
python scripts/run_realtime_component_sweep.py --run-id preview --dry-run
```

Run a small cached-model smoke before starting the full matrix:

```powershell
python scripts/run_realtime_component_sweep.py --run-id base_smoke --models base --max-cases 2
```

Run every enabled combination and resume after interruption:

```powershell
python scripts/run_realtime_component_sweep.py --run-id full_matrix
python scripts/run_realtime_component_sweep.py --run-id full_matrix --resume
```

The matrix lists Whisper tiny, base, small, medium, large-v1, large-v2,
large-v3, and large-v3-turbo. Larger models are disabled by default. Select
one explicitly with `--models small` or include every listed model with
`--all-models`. Downloads remain disabled unless
`--allow-model-downloads` is passed. Use `--devices cuda_fp16` to select the
disabled-by-default CUDA profile.

