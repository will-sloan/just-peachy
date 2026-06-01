# M14 Real Pipeline Completion Summary

M14 adds the practical real-model path on top of M13 without changing the
Evaluation Tool prediction contract.

High-level changes:

- Added a selectable external-stub inference config option.
- Added `configs/inference/e2e_real_local.yaml` for local Whisper tiny ASR,
  SpeechBrain ECAPA embeddings, and cosine speaker matching.
- Kept the smoke-safe M13 config as the default.
- Added CER scoring alongside existing WER outputs.
- Expanded diagnostics summary with speaker, threshold, RTF, and per-stage
  runtime metrics.
- Verified local Whisper and SpeechBrain assets are present and runnable.

Current blocker:

- The default enrollment DB is empty, so real known-speaker naming remains
  blocked until local speaker WAV samples are enrolled.

Primary run command:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full \
  --project-root "/Users/billy/Documents/just-peachy/Software Validation from Datasets" \
  --dataset cmu_arctic \
  --max-recordings 1 \
  --runner external-stub \
  --augmentation none \
  --inference-config configs/inference/e2e_real_local.yaml \
  --run-name m14_real_pipeline_config_smoke_v2
```

Observed real-config smoke metrics:

- Aggregate WER: `0.5000`
- Aggregate CER: `0.3243`
- Unknown rate: `1.0`
- False known-speaker assignment rate: `0.0`
- Pipeline RTF: `0.22537198493990465`

Detailed report:

- `Evaluation Tool/reports/milestones/M14_real_pipeline_completion_report.md`
