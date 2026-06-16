# Realtime Live Microphone Report

## Report Metadata
- Run id: `realtime_stitching_dry_or_wav_smoke`
- Date: `2026-06-08T14:00:42.239383+00:00`
- Config path: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml`
- Run directory: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.
- Added opt-in overlap-aware ASR stitching and delayed speaker-state handling for realtime validation runs.

## Difference From M17_VAL
- M17_VAL recorded one full chunk, paused capture while ASR ran, then recorded the next chunk.
- This prototype keeps capture and window assembly running while previous windows are processed by the worker, and records latency, backlog, and dropped-window diagnostics.

## How To Run
```bash
python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id realtime_stitching_dry_or_wav_smoke --duration-sec 32.2 --window-sec 2.0 --hop-sec 0.5 --speaker-label Unknown --keep-audio
```

## Execution Mode
- Microphone capture: not tested; dry-run or injected frames were used.
- ASR mode: configured ASR mode: whisper_base.
- Dry-run: `False`.
- Whisper package available: `True`.
- Whisper model asset: `/Users/billy/Documents/just-peachy/models/cache/whisper/base.pt`.
- Model downloads allowed: `False`.
- Config/runtime blocker: `none for completed run`.

## Realtime Stitching And Speaker Evidence
- Transcript stitching: enabled.
- Stability delay seconds: `1.0`.
- Speaker evidence window/hop seconds: `4.0` / `1.0`.
- Speaker confirmation: `2` of `3` windows above score `0.5`.
- Duplicate removal uses suffix/prefix token matching over normalized ASR tokens, with word timestamps converted from window-relative to stream-absolute time when ASR provides them.
- Provisional text remains mutable until the stability delay elapses; finalized text is committed without re-adding overlap tokens from later windows.
- Speaker evidence is accumulated over recent longer windows, with labels reported as `unknown`, `tentative`, or `confirmed`; recent transcript spans can be corrected when stronger evidence arrives.

## Latency And Backlog
- Windows completed: `90`.
- Predictions written: `59`.
- Dropped windows: `3`.
- Latency seconds: `{'count': 59, 'min': 0.175439, 'mean': 0.327753, 'max': 1.495563}`.
- ASR realtime factor: `{'count': 59, 'min': 0.072771, 'mean': 0.097914, 'max': 0.42436}`.
- Queue metrics: `{'max_depth_observed': 4, 'max_depth_recorded': 4.0, 'dropped_window_count': 3, 'dropped_window_indices': [46, 47, 22]}`.

## Commands Run
- `python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml --run-id realtime_stitching_dry_or_wav_smoke --input-wav artifacts/realtime_test_audio/aew_alt_rxr_eey_random_30s.wav --duration-sec 32.2 --window-sec 2.0 --hop-sec 0.5 --sample-rate 16000 --recording-id aew_rxr_eey_random_30s --stitch-transcript --verbose`

## Output Artifacts
- Predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/predictions/utterances.jsonl`
- Diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/predictions/diagnostics.jsonl`
- Summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/summary.json`
- Audio retained: `False`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
