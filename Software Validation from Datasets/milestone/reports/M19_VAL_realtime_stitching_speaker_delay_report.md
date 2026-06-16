# M19_VAL Realtime Stitching And Speaker Delay Report

## What Changed
- Implemented opt-in realtime ASR stitching for overlapping ASR windows.
- Added committed/provisional transcript state with a configurable stability delay.
- Added a longer-window speaker-evidence path and delayed speaker-label state.
- Added diagnostics fields for raw ASR text, normalized ASR text, overlap removals, committed/provisional text, speaker scores, speaker state, label status, and prior-span correction.
- Preserved the Evaluation Tool runner contract: each pipeline call still receives one record with `record["inference_audio_path"]`, and prediction rows still use `recording_id`, `utt_id`, `start_sec`, `end_sec`, `speaker_label`, and `text`.

## Files Changed
- `Software Validation from Datasets/Evaluation Tool/app/inference_pipeline/realtime/__init__.py`
- `Software Validation from Datasets/Evaluation Tool/app/inference_pipeline/realtime/stitching.py`
- `Software Validation from Datasets/Evaluation Tool/app/inference_pipeline/realtime/speaker_state.py`
- `Software Validation from Datasets/Evaluation Tool/scripts/live_mic_realtime.py`
- `Software Validation from Datasets/Evaluation Tool/tests/inference_pipeline/test_live_mic_realtime_stitching.py`
- `Software Validation from Datasets/Evaluation Tool/reports/component_reports/live_mic_realtime/live_mic_realtime_stitching_validation.md`

## Stitching Behavior
- Word timestamps are preferred when ASR provides them.
- Relative word timings are converted to stream-absolute timings by adding `window_start_sec`.
- When timings are missing, the stitcher falls back to normalized token matching.
- Duplicate removal uses fuzzy suffix/prefix matching so examples like `i do not blame you` plus `blame you for anything` become `i do not blame you for anything`.

## Speaker Behavior
- ASR updates can remain short and frequent.
- Longer speaker-evidence windows can run less frequently through `--speaker-window-sec` and `--speaker-hop-sec`.
- Speaker labels move through `unknown`, `tentative`, and `confirmed`.
- Repeated evidence is required before confirmation; weak evidence remains `Unknown`.
- Recent transcript spans can be corrected when stronger speaker evidence arrives later.

## Commands Run
```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_live_mic_realtime_stitching.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_live_mic_realtime.py tests/inference_pipeline/test_asr_interface.py tests/inference_pipeline/test_speaker_matching.py
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml --run-id realtime_stitching_dry_or_wav_smoke --input-wav artifacts/realtime_test_audio/aew_alt_rxr_eey_random_30s.wav --duration-sec 32.2 --window-sec 2.0 --hop-sec 0.5 --sample-rate 16000 --recording-id aew_rxr_eey_random_30s --stitch-transcript --verbose
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest
```

## Results
- Focused stitching tests: 7 passed.
- Existing realtime / ASR / speaker matching regression group: 30 passed.
- Full test suite: 178 passed, 1 Torch deprecation warning.
- Input-WAV smoke:
  - ASR prediction rows: 59
  - Speaker-evidence diagnostics: 28
  - Dropped-window diagnostics: 3 under default `drop_oldest`
  - Removed overlap tokens: 110 total across 32 ASR windows
  - Speaker label states: 42 confirmed rows, 12 tentative rows, 33 unknown rows
  - Rows with delayed prior-span correction: 14

## Artifacts
- Component report: `Software Validation from Datasets/Evaluation Tool/reports/component_reports/live_mic_realtime/live_mic_realtime_stitching_validation.md`
- Smoke run: `Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/`
- Smoke predictions: `Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/predictions/utterances.jsonl`
- Smoke diagnostics: `Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/predictions/diagnostics.jsonl`
- Smoke summary: `Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/summary.json`

## Remaining Incomplete Work
- The prototype does not claim production diarization quality.
- The speaker-evidence path still reuses the configured full `PipelineRunner.predict(...)` path, so speaker-only inference is not optimized yet.
- Fallback stitching is token-based and cannot fully solve ASR rewrites where the same phrase is paraphrased or heavily misrecognized across windows.
- GUI, cloud, scorer, dataset, training, and report-generator work remain out of scope for this milestone.
