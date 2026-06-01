# M15 Simple WAV Inference CLI Report

## Milestone

M15 - Simple WAV Inference CLI

## Summary

M15 adds a thin product-style CLI for direct WAV transcription without using
the Evaluation Tool full-run flow. The new script builds one synthetic pipeline
record per WAV, calls `PipelineRunner.predict()`, and writes concise output to
stdout. It does not create run folders, score results, build plots, or generate
reports by default.

## Files Changed

- `scripts/transcribe_wav.py`
- `configs/inference/presets/safe.yaml`
- `configs/inference/presets/tiny.yaml`
- `configs/inference/presets/base.yaml`
- `tests/inference_pipeline/test_transcribe_wav_cli.py`
- `reports/milestones/M15_simple_wav_inference_cli_report.md`

## CLI Usage

Human-readable output:

```bash
python scripts/transcribe_wav.py /path/to/audio.wav
```

Preset output:

```bash
python scripts/transcribe_wav.py /path/to/audio.wav --preset safe
python scripts/transcribe_wav.py /path/to/audio.wav --preset tiny
python scripts/transcribe_wav.py /path/to/audio.wav --preset base
```

Smoke-safe output:

```bash
python scripts/transcribe_wav.py /path/to/audio.wav --smoke-safe
```

JSON output:

```bash
python scripts/transcribe_wav.py /path/to/audio.wav \
  --config configs/inference/e2e_real_local.yaml \
  --format json
```

Multiple WAVs as JSONL:

```bash
python scripts/transcribe_wav.py first.wav second.wav --format jsonl
```

Optional diagnostics:

```bash
python scripts/transcribe_wav.py /path/to/audio.wav \
  --diagnostics /path/to/diagnostics.jsonl
```

Optional enrollment DB override:

```bash
python scripts/transcribe_wav.py /path/to/audio.wav \
  --enrollment-db artifacts/enrollment/enrollment_db.json
```

## Behavior

- Accepts one or more WAV files.
- Validates WAV suffix and file existence.
- Infers duration, sample rate, and channel count using `soundfile`.
- Builds a synthetic record with `recording_id`, `utt_id`,
  `inference_audio_path`, `start_sec`, and `end_sec`.
- Defaults IDs to the WAV stem.
- Supports `--recording-id`, `--utt-id`, `--start-sec`, and `--end-sec` for one
  WAV.
- Disallows `--recording-id` and `--utt-id` for multiple WAVs.
- Adds user-facing `--preset safe`, `--preset tiny`, and `--preset base`.
- Defaults to `--preset tiny` when present.
- Keeps `--smoke-safe` as an alias for `--preset safe`.
- Keeps `--config` for advanced full-config paths.
- Prints only concise transcript output to stdout unless JSON/JSONL is selected.
- Writes diagnostics only when `--diagnostics` is provided.
- Processes multiple WAVs independently and returns nonzero if any fail.
- Wires Whisper `beam_size` from config into the OpenAI Whisper adapter.

## Contract Preservation

The new CLI does not modify `ExternalStubRunner`, `run_evaluation.py`,
`predictions/utterances.jsonl`, scoring, plotting, reporting, or dataset
selection. It reuses the same `PipelineRunner.predict()` path and keeps
diagnostics separate from stdout.

## Test Commands

Run from `Software Validation from Datasets/Evaluation Tool`:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_transcribe_wav_cli.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_pipeline_e2e.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests -q -k "transcribe_wav or inference_pipeline or external_stub"
/Users/billy/Documents/just-peachy/.venv/bin/python -m compileall app/inference_pipeline app/model_runner app/scoring scripts
```

Results:

- Direct WAV CLI tests: `10 passed`
- Pipeline E2E tests: `9 passed`
- External stub bridge tests: `5 passed`
- Selected regression tests: `137 passed, 10 deselected, 1 warning`
- Compileall: passed

The warning is the existing Torch JIT Python 3.14 deprecation warning from the
Silero VAD test path.

## Smoke Commands

Smoke-safe direct CLI:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/transcribe_wav.py \
  "../RawDatasets/CMU Arctic/cmu_us_slt_arctic/wav/arctic_a0001.wav" \
  --preset safe
```

Result:

```text
[Unknown] dummy pipeline transcript
```

Real local direct CLI:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/transcribe_wav.py \
  "../RawDatasets/CMU Arctic/cmu_us_slt_arctic/wav/arctic_a0001.wav" \
  --preset tiny \
  --format json
```

Result:

```json
{"audio_path": "/Users/billy/Documents/just-peachy/Software Validation from Datasets/RawDatasets/CMU Arctic/cmu_us_slt_arctic/wav/arctic_a0001.wav", "end_sec": 3.355, "recording_id": "arctic_a0001", "speaker_label": "Unknown", "start_sec": 0.0, "text": "author of the danger trail, philip steals, etc.", "utt_id": "arctic_a0001"}
```

Whisper base preset:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/transcribe_wav.py \
  "../RawDatasets/CMU Arctic/cmu_us_slt_arctic/wav/arctic_a0001.wav" \
  --preset base \
  --format json
```

Result:

```json
{"audio_path": "/Users/billy/Documents/just-peachy/Software Validation from Datasets/RawDatasets/CMU Arctic/cmu_us_slt_arctic/wav/arctic_a0001.wav", "end_sec": 3.355, "recording_id": "arctic_a0001", "speaker_label": "Unknown", "start_sec": 0.0, "text": "author of the danger trail, philip steele's, etc.", "utt_id": "arctic_a0001"}
```

## Local Assets

Found:

- Whisper package in `.venv`
- Whisper tiny model:
  `/Users/billy/Documents/just-peachy/models/cache/whisper/tiny.pt`
- Whisper base model:
  `/Users/billy/Documents/just-peachy/models/cache/whisper/base.pt`
- SpeechBrain package in `.venv`
- SpeechBrain ECAPA local assets:
  `models/cache/speechbrain/spkrec-ecapa-voxceleb/`

## Remaining Work

- This is still offline WAV inference, not real-time microphone streaming.
- Unknown-speaker clustering and temporary voice profiles are not implemented.
- Known-speaker naming still requires a populated enrollment DB.
