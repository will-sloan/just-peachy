# Prompt 00 — repo audit

You are working in the existing Evaluation Tool repository.

## Task
Audit the repo and produce a short implementation note before writing any new model code.

## What to inspect
- `run_evaluation.py`
- `app/cli/main.py`
- `app/model_runner/base.py`
- `app/model_runner/external_stub.py`
- `app/prediction_io/schema.py`
- any code path that writes `predictions/utterances.jsonl`
- any code path that calls `predict_one()`
- any run-config field relevant to external runner setup

## What to produce
Create `docs/onnx_pipeline_audit.md` containing:
1. the current `external_stub.py` integration shape
2. what object `predict_one()` must return
3. where model config should be loaded from
4. whether runner instances are created once per run or per record
5. which fields from the record dict are guaranteed
6. exact file path recommendations for new ONNX pipeline code

## Constraints
- Do not change any existing behavior yet.
- Do not add model code yet.
- Do not redesign the harness.

## Acceptance criteria
- `docs/onnx_pipeline_audit.md` exists
- the note explicitly confirms the prediction key contract `(recording_id, utt_id)`
- the note explicitly confirms that inference must use `record["inference_audio_path"]`
- the note explicitly confirms how `start_sec` / `end_sec` should be handled
