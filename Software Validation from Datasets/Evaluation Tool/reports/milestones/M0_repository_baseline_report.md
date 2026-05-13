# M0 Repository Baseline Report

## Summary

M0 created the inference pipeline documentation baseline without adding model
code or changing the existing Evaluation Tool runtime behavior.

Changed files:

- `README_inference_pipeline.md`
- `docs/inference_pipeline/FILE_MAP.md`
- `docs/inference_pipeline/DEVELOPMENT_RULES.md`
- `docs/inference_pipeline/MILESTONE_LEDGER.md`
- `reports/milestones/M0_repository_baseline_report.md`
- `tests/test_m0_docs.py`

## Inspected Files

- `app/model_runner/external_stub.py`
- `app/model_runner/base.py`
- `app/prediction_io/schema.py`
- `app/prediction_io/jsonl.py`
- `prompts/external_runner_prompt.md`
- `app/cli/main.py`
- `app/dataset_registry/registry.py`
- `requirements.txt`

## Runner Contract Captured

The external runner contract is captured in
`docs/inference_pipeline/FILE_MAP.md`. Future prompts can copy the contract from
that file. The key M0 rules are:

- the model must read `record["inference_audio_path"]`
- `recording_id` and `utt_id` must be preserved exactly
- `start_sec` and `end_sec` must be preserved when present
- predictions must be written to `predictions/utterances.jsonl`
- utterance rows must include `recording_id`, `utt_id`, `start_sec`, `end_sec`,
  `speaker_label`, and `text`

## Testing and Smoke Checks

Commands to run from `Software Validation from Datasets/Evaluation Tool`:

```powershell
& '..\..\myenv\Scripts\python.exe' -m pytest tests/test_m0_docs.py
```

Commands to run from repository root:

```powershell
git status --short
```

Observed results in this shell:

- `& '..\..\myenv\Scripts\python.exe' -m pytest tests/test_m0_docs.py` passed
  with the docs and protected-path checks.
- `git status --short --untracked-files=all -- "Software Validation from Datasets/Evaluation Tool"`
  showed only M0 docs, report, and docs validation tests.

## Safety Confirmation

M0 did not intentionally change:

- scorer: `app/scoring/`
- dataset registry: `app/dataset_registry/`
- GUI: `app/gui/`
- CLI: `app/cli/`
- plotting: `app/plotting/`
- reporting: `app/reporting/`
- normalized metadata loading: `app/dataset_registry/loader.py`
- read-only runner file: `app/model_runner/external_stub.py`
- read-only prediction schema: `app/prediction_io/schema.py`

## Open Issues

The local virtual environment `myenv/` exists at the repository root and is
untracked. It is outside the M0 artifact set, so keep it outside any
documentation-only commit.
