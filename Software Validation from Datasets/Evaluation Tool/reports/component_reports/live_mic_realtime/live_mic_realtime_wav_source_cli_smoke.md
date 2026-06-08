# Realtime Live Microphone Report

## Report Metadata
- Run id: `wav_source_cli_smoke`
- Date: `2026-06-05T13:59:29.337169+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_realtime_whisper_tiny.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/wav_source_cli_smoke`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.

## Difference From M17_VAL
- M17_VAL recorded one full chunk, paused capture while ASR ran, then recorded the next chunk.
- This prototype keeps capture and window assembly running while previous windows are processed by the worker, and records latency, backlog, and dropped-window diagnostics.

## How To Run
```bash
python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id wav_source_cli_smoke --duration-sec 1.0 --window-sec 0.5 --hop-sec 0.5 --speaker-label Billy --keep-audio
```

## Execution Mode
- Microphone capture: not tested; dry-run or injected frames were used.
- ASR mode: dry-run no-op ASR; transcripts are contract placeholders, not real ASR.
- Dry-run: `True`.
- Whisper package available: `True`.
- Whisper model asset: `/Users/billy/Documents/just-peachy/models/cache/whisper/tiny.pt`.
- Model downloads allowed: `False`.
- Config/runtime blocker: `none for completed run`.

## Latency And Backlog
- Windows completed: `2`.
- Predictions written: `2`.
- Dropped windows: `0`.
- Latency seconds: `{'count': 2, 'min': 0.005332, 'mean': 0.006563, 'max': 0.007794}`.
- ASR realtime factor: `{'count': 2, 'min': 0.000286, 'mean': 0.000416, 'max': 0.000546}`.
- Queue metrics: `{'max_depth_observed': 1, 'max_depth_recorded': 1.0, 'dropped_window_count': 0, 'dropped_window_indices': []}`.

## Commands Run
- `python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id wav_source_cli_smoke --duration-sec 1 --window-sec 0.5 --hop-sec 0.5 --sample-rate 16000 --speaker-label Billy --recording-id wav_source --input-wav m9_test/audio/a1.wav --dry-run`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/wav_source_cli_smoke/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/wav_source_cli_smoke/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/wav_source_cli_smoke/summary.json`
- Audio retained: `False`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
