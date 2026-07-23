# Realtime Live Microphone Report

## Report Metadata
- Run id: `aew_alt_rxr_eey_random_30s_matching`
- Date: `2026-07-03T14:55:11.400016+00:00`
- Config path: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\inference\live_mic_realtime_whisper_base_speaker_matching.yaml`
- Run directory: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\runs\live_mic_realtime\aew_alt_rxr_eey_random_30s_matching`

## What Changed
- Added a genuine realtime microphone prototype with continuous frame capture, fixed inference windows, a bounded background inference queue, and a worker that calls `PipelineRunner.predict(...)`.
- Preserved the file-backed Evaluation Tool contract by writing every processed window to WAV and passing it through `record["inference_audio_path"]`.
- Added opt-in overlap-aware ASR stitching and delayed speaker-state handling for realtime validation runs.

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
- Whisper model asset: `C:\Users\amiri\Documents\GitHub\just-peachy\models\cache\whisper\base.pt`.
- Model downloads allowed: `False`.
- Config/runtime blocker: `none for completed run`.

## Realtime Stitching And Speaker Evidence
- Transcript stitching: disabled; one prediction row is emitted per ASR window.
- Duplicate removal uses suffix/prefix token matching over normalized ASR tokens, with word timestamps converted from window-relative to stream-absolute time when ASR provides them.
- Provisional text remains mutable until the stability delay elapses; finalized text is committed without re-adding overlap tokens from later windows.
- Speaker evidence is accumulated over recent longer windows, with labels reported as `unknown`, `tentative`, or `confirmed`; recent transcript spans can be corrected when stronger evidence arrives.

## Latency And Backlog
- Windows completed: `3`.
- Predictions written: `0`.
- Dropped windows: `0`.
- Latency seconds: `{'count': 0, 'min': None, 'mean': None, 'max': None}`.
- ASR realtime factor: `{'count': 0, 'min': None, 'mean': None, 'max': None}`.
- Queue metrics: `{'max_depth_observed': 2, 'max_depth_recorded': 1.0, 'dropped_window_count': 0, 'dropped_window_indices': []}`.

## Commands Run
- `python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml --run-id aew_alt_rxr_eey_random_30s_matching --input-wav artifacts/realtime_test_audio/aew_alt_rxr_eey_random_30s.wav --duration-sec 32.2 --window-sec 3.0 --hop-sec 3.0 --sample-rate 16000 --recording-id aew_alt_rxr_eey_random_30s`

## Output Artifacts
- Predictions: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\runs\live_mic_realtime\aew_alt_rxr_eey_random_30s_matching\predictions\utterances.jsonl`
- Diagnostics: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\runs\live_mic_realtime\aew_alt_rxr_eey_random_30s_matching\predictions\diagnostics.jsonl`
- Summary: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\runs\live_mic_realtime\aew_alt_rxr_eey_random_30s_matching\summary.json`
- Audio retained: `False`

## Remaining Incomplete Work
- Run a non-dry microphone smoke after `sounddevice`, OS microphone permission, Whisper package, and local model assets are available.
