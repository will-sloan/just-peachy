# Live Microphone Smoke Report

## Report Metadata
- Run id: `m17_val_dry_run`
- Date: `2026-06-03T14:10:23.493193+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_whisper_tiny.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/m17_val_dry_run`

## What Changed
- Added a file-backed live microphone smoke path that records each chunk to WAV and calls `PipelineRunner.predict(...)` with `record["inference_audio_path"]`.
- Preserved the existing utterance prediction contract: `recording_id, utt_id, start_sec, end_sec, speaker_label, text`.

## How To Run
```bash
python scripts/live_mic_smoke.py --config configs/inference/live_mic_whisper_tiny.yaml --run-id m17_val_dry_run --duration-sec 0.3 --chunk-sec 0.15 --sample-rate 16000 --speaker-label Billy --keep-audio
```

## Execution Mode
- Microphone capture: not tested; dry-run generated synthetic WAV chunks.
- Microphone dependency available: `False`.
- Real microphone blocker: `missing optional dependency 'sounddevice'`.
- ASR mode: dry-run no-op ASR.
- Dry-run: `True`.
- Whisper package available: `True`.
- Whisper model asset: `/Users/billy/Documents/just-peachy/models/cache/whisper/tiny.pt`.
- Model downloads allowed: `False`.
- ASR/config blocker: `none for completed run`.

## Commands Run
- `python scripts/live_mic_smoke.py --config configs/inference/live_mic_whisper_tiny.yaml --run-id m17_val_dry_run --duration-sec 0.3 --chunk-sec 0.15 --speaker-label Billy --dry-run`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/m17_val_dry_run/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/m17_val_dry_run/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/m17_val_dry_run/summary.json`
- Audio retained: `False`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
