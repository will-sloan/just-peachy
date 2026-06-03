# M17_VAL Live Microphone End-to-End Smoke Validation

## What Changed

- Added `Evaluation Tool/scripts/live_mic_smoke.py`, a file-backed microphone smoke harness that writes each chunk to a WAV file and calls `PipelineRunner.predict(...)` with `record["inference_audio_path"]`.
- Added `Evaluation Tool/configs/inference/live_mic_whisper_tiny.yaml`, selecting `whisper_tiny` with downloads disabled and unrelated VAD, diarization, speaker embedding, and speaker matching components disabled.
- Added focused tests using fake microphone capture and fake pipeline behavior. No automated test requires microphone hardware or Whisper model downloads.
- Added a live mic component report at `Evaluation Tool/reports/component_reports/live_mic/live_mic_smoke_m17_val_dry_run.md`.

## How To Run

```bash
cd "/Users/billy/Documents/just-peachy"
source .venv/bin/activate
cd "Software Validation from Datasets/Evaluation Tool"
python scripts/live_mic_smoke.py \
  --config configs/inference/live_mic_whisper_tiny.yaml \
  --run-id manual_mic_test \
  --duration-sec 10 \
  --chunk-sec 3 \
  --speaker-label Billy \
  --keep-audio
```

For dependency-free contract validation:

```bash
python scripts/live_mic_smoke.py \
  --config configs/inference/live_mic_whisper_tiny.yaml \
  --run-id m17_val_dry_run \
  --duration-sec 0.3 \
  --chunk-sec 0.15 \
  --speaker-label Billy \
  --dry-run
```

## Local Execution Status

- Microphone capture actually tested: no.
- Local blocker for real microphone capture: `sounddevice` is not installed in the active `.venv`.
- Whisper package available: yes.
- Whisper tiny model asset available: yes, at `/Users/billy/Documents/just-peachy/models/cache/whisper/tiny.pt`.
- Model downloads allowed by the live mic config: no.
- Completed smoke mode: dry-run, with synthetic WAV chunks and explicit no-op transcript text `dry run transcript unavailable`.
- Real ASR end-to-end over live microphone audio: not run because microphone capture was unavailable.

## Commands Run

- `git status --short`
- `git checkout m17_val`
- `source .venv/bin/activate && python --version`
- `python -m pytest tests/inference_pipeline/test_live_mic_smoke.py`
- `python -m pytest tests/inference_pipeline/test_pipeline_e2e.py tests/inference_pipeline/test_asr_interface.py`
- `python -m pytest`
- `python scripts/live_mic_smoke.py --config configs/inference/live_mic_whisper_tiny.yaml --run-id m17_val_dry_run --duration-sec 0.3 --chunk-sec 0.15 --speaker-label Billy --dry-run`
- Python availability probe for `sounddevice`, `whisper`, `soundfile`, and `torch`

## Results

- Focused live mic tests: `5 passed`.
- Existing E2E and ASR interface tests: `14 passed`.
- Full Evaluation Tool test suite: `160 passed, 1 warning`.
- Dry-run live mic smoke: completed with 2 chunks and 2 prediction rows.

## Output Artifacts

- Dry-run predictions: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/m17_val_dry_run/predictions/utterances.jsonl`
- Dry-run diagnostics: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/m17_val_dry_run/predictions/diagnostics.jsonl`
- Dry-run summary: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/runs/live_mic/m17_val_dry_run/summary.json`
- Component report: `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/reports/component_reports/live_mic/live_mic_smoke_m17_val_dry_run.md`

## Remaining Incomplete Work

- Install `sounddevice` in the repository `.venv` and grant OS microphone permission to run real microphone capture.
- After microphone capture works, run the manual command above to validate real Whisper tiny transcription over live microphone chunks.
- No diarization, dataset, GUI, scorer, or report-generator changes were made for this milestone.
