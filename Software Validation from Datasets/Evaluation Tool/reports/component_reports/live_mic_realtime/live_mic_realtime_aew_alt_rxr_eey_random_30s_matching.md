# Realtime Live Microphone Report

## Report Metadata
- Run id: `aew_alt_rxr_eey_random_30s_matching`
- Date: `2026-06-05T15:39:11.505446+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_alt_rxr_eey_random_30s_matching`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.

## Difference From M17_VAL
- M17_VAL recorded one full chunk, paused capture while ASR ran, then recorded the next chunk.
- This prototype keeps capture and window assembly running while previous windows are processed by the worker, and records latency, backlog, and dropped-window diagnostics.

## How To Run
```bash
python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id aew_alt_rxr_eey_random_30s_matching --duration-sec 32.2 --window-sec 3.0 --hop-sec 3.0 --speaker-label Unknown --keep-audio
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
- Windows completed: `10`.
- Predictions written: `10`.
- Dropped windows: `0`.
- Latency seconds: `{'count': 10, 'min': 0.215268, 'mean': 0.29872, 'max': 0.902426}`.
- ASR realtime factor: `{'count': 10, 'min': 0.062178, 'mean': 0.08316, 'max': 0.225133}`.
- Queue metrics: `{'max_depth_observed': 1, 'max_depth_recorded': 1.0, 'dropped_window_count': 0, 'dropped_window_indices': []}`.

## Commands Run
- `python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml --run-id aew_alt_rxr_eey_random_30s_matching --input-wav artifacts/realtime_test_audio/aew_alt_rxr_eey_random_30s.wav --duration-sec 32.2 --window-sec 3.0 --hop-sec 3.0 --sample-rate 16000 --recording-id aew_alt_rxr_eey_random_30s`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_alt_rxr_eey_random_30s_matching/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_alt_rxr_eey_random_30s_matching/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_alt_rxr_eey_random_30s_matching/summary.json`
- Audio retained: `False`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
