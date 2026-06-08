# M18_VAL Realtime Live Microphone Report

## What Changed
- Added `scripts/live_mic_realtime.py`, a developer validation prototype that continuously captures audio frames while a background worker processes completed inference windows.
- Added realtime Whisper configs:
  - `configs/inference/live_mic_realtime_whisper_tiny.yaml`
  - `configs/inference/live_mic_realtime_whisper_base.yaml`
- Added fake-capture/fake-pipeline tests in `tests/inference_pipeline/test_live_mic_realtime.py`.
- Added per-run realtime outputs under `runs/live_mic_realtime/<run_id>/` and component reports under `reports/component_reports/live_mic_realtime/`.

## Difference From M17_VAL
- M17_VAL `live_mic_smoke.py` records a complete chunk, stops capture while `PipelineRunner.predict(...)` runs, then records the next chunk.
- M18_VAL `live_mic_realtime.py` uses a producer-consumer design:
  - `sounddevice.InputStream` callback or dry-run source captures frames continuously.
  - A window producer assembles fixed windows with optional overlap.
  - A bounded inference queue applies `drop_oldest`, `drop_newest`, or `block`.
  - A background worker writes each window to WAV and calls the unchanged file-backed `PipelineRunner.predict(...)` contract.

## How To Run
Dry-run validation:
```bash
python scripts/live_mic_realtime.py \
  --config configs/inference/live_mic_realtime_whisper_tiny.yaml \
  --run-id m18_realtime_dry_run \
  --duration-sec 3 \
  --window-sec 1.0 \
  --hop-sec 0.5 \
  --speaker-label Billy \
  --dry-run
```

Manual microphone validation, not required by automated tests:
```bash
python scripts/live_mic_realtime.py \
  --config configs/inference/live_mic_realtime_whisper_tiny.yaml \
  --run-id manual_realtime_mic_test \
  --duration-sec 20 \
  --window-sec 3 \
  --hop-sec 1.5 \
  --speaker-label Billy \
  --keep-audio
```

## Execution Status
- Microphone capture actually tested: no. This pass used dry-run synthetic frames so automated validation did not require microphone hardware or OS microphone permission.
- Real ASR used in the measured run: no. Dry-run intentionally used `dry_run_no_op_asr`, and transcript text is marked as unavailable rather than presented as real ASR.
- Whisper package available: yes.
- `sounddevice` package available: yes.
- Whisper tiny asset available: yes, `/Users/billy/Documents/just-peachy/models/cache/whisper/tiny.pt`.
- Whisper base asset available: yes, `/Users/billy/Documents/just-peachy/models/cache/whisper/base.pt`.
- Model downloads allowed by realtime configs: no.

## Dry-Run Metrics
- Run id: `m18_realtime_dry_run`
- Windows completed: 5
- Predictions written: 5
- Dropped windows: 0
- Queue max depth observed: 1
- Latency seconds: min `0.004013`, mean `0.004703`, max `0.006333`
- ASR realtime factor: no-op dry-run values only; min `0.000022`, mean `0.000053`, max `0.000156`

## Commands Run
```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_live_mic_realtime.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_live_mic_smoke.py tests/inference_pipeline/test_pipeline_e2e.py tests/inference_pipeline/test_asr_interface.py
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/live_mic_realtime.py --config configs/inference/live_mic_realtime_whisper_tiny.yaml --run-id m18_realtime_dry_run --duration-sec 3 --window-sec 1.0 --hop-sec 0.5 --speaker-label Billy --dry-run
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest
```

## Output Artifacts
- Predictions: `Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/m18_realtime_dry_run/predictions/utterances.jsonl`
- Diagnostics: `Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/m18_realtime_dry_run/predictions/diagnostics.jsonl`
- Summary: `Software Validation from Datasets/Evaluation Tool/runs/live_mic_realtime/m18_realtime_dry_run/summary.json`
- Component report: `Software Validation from Datasets/Evaluation Tool/reports/component_reports/live_mic_realtime/live_mic_realtime_m18_realtime_dry_run.md`

## Remaining Incomplete Work
- Run the non-dry manual microphone command locally to measure real microphone capture and real Whisper latency.
- Transcript stitching across overlapping windows remains future work; this milestone records `window_start_sec` and `window_end_sec` metadata for that later step.
- Production streaming behavior, GUI integration, cloud execution, training, scorer changes, and speaker matching are intentionally out of scope.
