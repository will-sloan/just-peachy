# M1 Contracts Report

## Summary

M1 added model-free inference pipeline contracts. No VAD, ASR, speaker
embedding, diarization, model loading, GPU code, Raspberry Pi optimization,
ExecuTorch export, or external hardware integration was implemented.

Changed files:

- `app/inference_pipeline/__init__.py`
- `app/inference_pipeline/contracts.py`
- `app/inference_pipeline/errors.py`
- `app/inference_pipeline/typing.py`
- `tests/inference_pipeline/test_contracts.py`
- `docs/inference_pipeline/contracts.md`
- `docs/inference_pipeline/MILESTONE_LEDGER.md`
- `reports/milestones/M1_contracts_report.md`

## Contracts Added

- `EvaluationRecord`
- `AudioSegment`
- `SpeechRegion`
- `WordTiming`
- `ASRTranscript`
- `SpeakerEmbedding`
- `SpeakerDecision`
- `TranscriptItem`
- `RuntimeStats`
- `PipelineOutput`

## Runner Contract Preservation

The existing Evaluation Tool runner contract is preserved. The new contracts do
not modify `app/model_runner/external_stub.py`, `app/model_runner/base.py`, or
`app/prediction_io/schema.py`.

`EvaluationRecord.from_record(...)` requires `record["inference_audio_path"]`
and preserves `recording_id`, `utt_id`, `start_sec`, and `end_sec`.
`PipelineOutput.to_utterance_prediction_row()` returns exactly the required
`predictions/utterances.jsonl` fields:

- `recording_id`
- `utt_id`
- `start_sec`
- `end_sec`
- `speaker_label`
- `text`

## Validation Commands

Run from `Software Validation from Datasets\Evaluation Tool`:

```powershell
& '..\..\myenv\Scripts\python.exe' -m pytest tests\inference_pipeline\test_contracts.py
& '..\..\myenv\Scripts\python.exe' -m pytest tests\test_m0_docs.py
```

Run from repository root:

```powershell
git status --short -- "Software Validation from Datasets\Evaluation Tool\app\model_runner" "Software Validation from Datasets\Evaluation Tool\app\prediction_io" "Software Validation from Datasets\Evaluation Tool\app\scoring" "Software Validation from Datasets\Evaluation Tool\app\dataset_registry" "Software Validation from Datasets\Evaluation Tool\app\gui" "Software Validation from Datasets\Evaluation Tool\app\cli" "Software Validation from Datasets\Evaluation Tool\app\plotting" "Software Validation from Datasets\Evaluation Tool\app\reporting"
```

## Test Results

- `tests\inference_pipeline\test_contracts.py`: 11 passed.
- `tests\test_m0_docs.py`: 5 passed.

## Safety Confirmation

The protected-path check returned no changed files for:

- `app/model_runner`
- `app/prediction_io`
- `app/scoring`
- `app/dataset_registry`
- `app/gui`
- `app/cli`
- `app/plotting`
- `app/reporting`

## Open Issues

None known.
