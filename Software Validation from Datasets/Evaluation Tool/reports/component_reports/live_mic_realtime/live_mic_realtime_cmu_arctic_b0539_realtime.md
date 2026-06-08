# Realtime Live Microphone Report

## Report Metadata
- Run id: `cmu_arctic_b0539_realtime`
- Date: `2026-06-05T14:34:38.223180+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_realtime_whisper_base.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/cmu_arctic_b0539_realtime`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.

## Difference From M17_VAL
- M17_VAL recorded one full chunk, paused capture while ASR ran, then recorded the next chunk.
- This prototype keeps capture and window assembly running while previous windows are processed by the worker, and records latency, backlog, and dropped-window diagnostics.

## How To Run
```bash
python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id cmu_arctic_b0539_realtime --duration-sec 3.3 --window-sec 1.0 --hop-sec 0.5 --speaker-label Billy --keep-audio
```

## Execution Mode
- Microphone capture: not tested; dry-run or injected frames were used.
- ASR mode: configured ASR mode: whisper_base.
- Dry-run: `False`.
- Whisper package available: `True`.
- Whisper model asset: `/Users/billy/Documents/just-peachy/models/cache/whisper/base.pt`.
- Model downloads allowed: `False`.
- Config/runtime blocker: `none for completed run`.

## Latency And Backlog
- Windows completed: `5`.
- Predictions written: `5`.
- Dropped windows: `0`.
- Latency seconds: `{'count': 5, 'min': 0.172378, 'mean': 0.305702, 'max': 0.678312}`.
- ASR realtime factor: `{'count': 5, 'min': 0.143375, 'mean': 0.268715, 'max': 0.67212}`.
- Queue metrics: `{'max_depth_observed': 1, 'max_depth_recorded': 1.0, 'dropped_window_count': 0, 'dropped_window_indices': []}`.

## Commands Run
- `python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_base.yaml --run-id cmu_arctic_b0539_realtime --input-wav ../RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_b0538.wav --duration-sec 3.3 --window-sec 1.0 --hop-sec 0.5 --sample-rate 16000 --speaker-label Billy --recording-id cmu_arctic_b0539 --keep-audio`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/cmu_arctic_b0539_realtime/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/cmu_arctic_b0539_realtime/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/cmu_arctic_b0539_realtime/summary.json`
- Audio retained: `True`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
