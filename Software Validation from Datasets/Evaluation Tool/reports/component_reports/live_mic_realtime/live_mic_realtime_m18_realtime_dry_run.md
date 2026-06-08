# Realtime Live Microphone Report

## Report Metadata
- Run id: `m18_realtime_dry_run`
- Date: `2026-06-04T14:31:26.604207+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_realtime_whisper_tiny.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/m18_realtime_dry_run`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.

## Difference From M17_VAL
- M17_VAL recorded one full chunk, paused capture while ASR ran, then recorded the next chunk.
- This prototype keeps capture and window assembly running while previous windows are processed by the worker, and records latency, backlog, and dropped-window diagnostics.

## How To Run
```bash
python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id m18_realtime_dry_run --duration-sec 3.0 --window-sec 1.0 --hop-sec 0.5 --speaker-label Billy --keep-audio
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
- Windows completed: `5`.
- Predictions written: `5`.
- Dropped windows: `0`.
- Latency seconds: `{'count': 5, 'min': 0.004013, 'mean': 0.004703, 'max': 0.006333}`.
- ASR realtime factor: `{'count': 5, 'min': 2.2e-05, 'mean': 5.3e-05, 'max': 0.000156}`.
- Queue metrics: `{'max_depth_observed': 1, 'max_depth_recorded': 1.0, 'dropped_window_count': 0, 'dropped_window_indices': []}`.

## Commands Run
- `python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id m18_realtime_dry_run --duration-sec 3 --window-sec 1.0 --hop-sec 0.5 --speaker-label Billy --dry-run`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/m18_realtime_dry_run/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/m18_realtime_dry_run/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/m18_realtime_dry_run/summary.json`
- Audio retained: `False`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
