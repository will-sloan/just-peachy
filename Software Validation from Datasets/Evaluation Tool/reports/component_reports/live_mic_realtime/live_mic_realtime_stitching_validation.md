# Realtime ASR Stitching And Delayed Speaker Evidence Report

## What Changed
- Added `app/inference_pipeline/realtime/stitching.py` for overlap-aware realtime transcript stitching.
- Added `app/inference_pipeline/realtime/speaker_state.py` for `unknown` / `tentative` / `confirmed` speaker-label state.
- Extended `scripts/live_mic_realtime.py` with opt-in stitching and delayed speaker-evidence flags while preserving the existing default per-window behavior.
- Added `tests/inference_pipeline/test_live_mic_realtime_stitching.py` with model-free tests for overlap removal, timestamp conversion, stability delay, speaker evidence, and quiet output.

## Overlap Duplicate Removal
- The stitcher converts each ASR window into normalized tokens.
- If ASR provides word timings, word start/end times are converted from window-relative to stream-absolute time with `window_start_sec`.
- If word timings are unavailable, the stitcher uses token fallback timing across the ASR window and fuzzy suffix/prefix matching over normalized tokens.
- Only the non-overlapping suffix of each new ASR window is appended to the transcript state.

## Provisional And Final Text
- The stitcher maintains committed words and provisional words.
- Words remain provisional until `window_end_sec - stability_delay_sec` passes their end time.
- Quiet output uses `Speaker?: ...` for provisional text and `Speaker: ...` for finalized text.
- `provisional_delta_text` only contains newly appended words that remain provisional, so quiet output does not reprint words that became committed in the same update.

## Delayed Speaker Evidence
- ASR windows remain short and frequent.
- When stitching is enabled, longer speaker-evidence windows are assembled separately from the same frame stream.
- The current prototype feeds those longer windows through the unchanged file-backed `PipelineRunner.predict(...)` contract and consumes speaker scores from diagnostics.
- `SpeakerEvidenceAccumulator` confirms a label after repeated recent evidence clears the score threshold. Weak evidence returns `Unknown`.
- Recent transcript spans are eligible for delayed correction when new speaker evidence arrives.

## Commands Run
```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_live_mic_realtime_stitching.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_live_mic_realtime.py tests/inference_pipeline/test_asr_interface.py tests/inference_pipeline/test_speaker_matching.py
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml --run-id realtime_stitching_dry_or_wav_smoke --input-wav artifacts/realtime_test_audio/aew_alt_rxr_eey_random_30s.wav --duration-sec 32.2 --window-sec 2.0 --hop-sec 0.5 --sample-rate 16000 --recording-id aew_rxr_eey_random_30s --stitch-transcript --verbose
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest
```

## Validation Results
- Focused stitching tests: 7 passed.
- Existing realtime / ASR / speaker matching regression group: 30 passed.
- Full suite: 178 passed, 1 Torch deprecation warning.
- Input-WAV smoke status counts: 59 ASR prediction rows, 28 speaker-evidence diagnostics, 3 dropped-window diagnostics under the requested default `drop_oldest` queue policy.
- Smoke overlap removals: 110 total removed overlap tokens across 32 ASR windows.
- Smoke speaker states: 42 confirmed rows, 12 tentative rows, 33 unknown rows, 14 rows with recent-span correction.

## Output Artifacts
- Smoke run directory: `runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/`
- Smoke predictions: `runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/predictions/utterances.jsonl`
- Smoke diagnostics: `runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/predictions/diagnostics.jsonl`
- Smoke summary: `runs/live_mic_realtime/realtime_stitching_dry_or_wav_smoke/summary.json`
- Generated smoke component report: `reports/component_reports/live_mic_realtime/live_mic_realtime_realtime_stitching_dry_or_wav_smoke.md`

## Limitations
- The smoke ASR output did not include word timestamps, so fallback token timing was used.
- Fuzzy suffix/prefix matching removes contiguous overlap; ASR rewrites that change many neighboring words can still leave repeated meaning.
- The separate speaker-evidence path currently reuses `PipelineRunner.predict(...)`, so configured ASR also runs on speaker windows.
- No production diarization model quality is claimed in this milestone.
- GUI, cloud execution, scorer, dataset, report-generator, and training behavior were intentionally left unchanged.
