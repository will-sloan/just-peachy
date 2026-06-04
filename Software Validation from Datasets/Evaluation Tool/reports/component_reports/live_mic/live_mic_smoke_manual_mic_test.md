# Live Microphone Smoke Report

## Report Metadata
- Run id: `manual_mic_test`
- Date: `2026-06-04T14:12:00.150099+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_whisper_base.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/manual_mic_test`

## What Changed
- Added a file-backed live microphone smoke path that records each chunk to WAV and calls `PipelineRunner.predict(...)` with `record["inference_audio_path"]`.
- Preserved the existing utterance prediction contract: `recording_id, utt_id, start_sec, end_sec, speaker_label, text`.

## How To Run
```bash
python scripts/live_mic_smoke.py --config configs/inference/live_mic_whisper_tiny.yaml --run-id manual_mic_test --duration-sec 10 --chunk-sec 3 --sample-rate 16000 --speaker-label Billy --keep-audio
```

## Execution Mode
- Microphone capture: actual microphone capture was attempted.
- Microphone dependency available: `True`.
- Real microphone blocker: `none for completed run`.
- ASR mode: configured real ASR: whisper_base.
- Dry-run: `False`.
- Whisper package available: `True`.
- Whisper model asset: `/Users/billy/Documents/just-peachy/models/cache/whisper/base.pt`.
- Model downloads allowed: `False`.
- ASR/config blocker: `none for completed run`.

## Commands Run
- `python scripts/live_mic_smoke.py --config configs/inference/live_mic_whisper_base.yaml --run-id manual_mic_test --duration-sec 10 --chunk-sec 3 --speaker-label Billy --keep-audio`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/manual_mic_test/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/manual_mic_test/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/manual_mic_test/summary.json`
- Audio retained: `True`

## Remaining Incomplete Work
- No incomplete work was identified by this smoke run.
