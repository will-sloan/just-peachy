# Realtime Live Microphone Report

## Report Metadata
- Run id: `aew_rxr_eey_concat_matching`
- Date: `2026-06-05T15:33:40.280576+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_rxr_eey_concat_matching`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.

## Difference From M17_VAL
- M17_VAL recorded one full chunk, paused capture while ASR ran, then recorded the next chunk.
- This prototype keeps capture and window assembly running while previous windows are processed by the worker, and records latency, backlog, and dropped-window diagnostics.

## How To Run
```bash
python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id aew_rxr_eey_concat_matching --duration-sec 9.0 --window-sec 3.0 --hop-sec 1.5 --speaker-label Unknown --keep-audio
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
- Windows completed: `4`.
- Predictions written: `4`.
- Dropped windows: `0`.
- Latency seconds: `{'count': 4, 'min': 0.215437, 'mean': 0.976031, 'max': 2.568924}`.
- ASR realtime factor: `{'count': 4, 'min': 0.061429, 'mean': 0.295328, 'max': 0.833647}`.
- Queue metrics: `{'max_depth_observed': 1, 'max_depth_recorded': 1.0, 'dropped_window_count': 0, 'dropped_window_indices': []}`.

## Commands Run
- `python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml --run-id aew_rxr_eey_concat_matching --input-wav artifacts/realtime_test_audio/aew_rxr_eey_arctic_a0301_concat.wav --duration-sec 9.0 --window-sec 3.0 --hop-sec 1.5 --sample-rate 16000 --recording-id aew_rxr_eey_arctic_a0301_concat`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_rxr_eey_concat_matching/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_rxr_eey_concat_matching/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/aew_rxr_eey_concat_matching/summary.json`
- Audio retained: `False`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
