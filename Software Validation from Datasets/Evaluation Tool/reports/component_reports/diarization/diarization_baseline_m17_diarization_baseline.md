# Diarization Baseline Report

## Milestone

M17 - Optional Diarization and Overlap Baseline

- Run id: `m17_diarization_baseline`
- Selected diarization backend: `no_op_diarization` by default; `pyannote_community` is available only as an optional config path
- Pyannote status: blocked for real execution because `pyannote` is not installed in the repository `.venv`

## Files Changed

- `app/inference_pipeline/diarization/__init__.py`
- `app/inference_pipeline/diarization/base.py`
- `app/inference_pipeline/diarization/pyannote_adapter.py`
- `app/inference_pipeline/config.py`
- `app/inference_pipeline/contracts.py`
- `app/inference_pipeline/pipeline.py`
- `app/inference_pipeline/registry.py`
- `app/inference_pipeline/runtime/stats.py`
- `configs/inference/components/diarization/pyannote_community.yaml`
- `configs/inference/base.yaml`
- `configs/inference/cpu_smoke.yaml`
- `configs/inference/desktop_gpu.yaml`
- `configs/inference/e2e_named_transcript.yaml`
- `configs/inference/raspberry_pi_future.yaml`
- `tests/inference_pipeline/test_diarization_interface.py`
- `tests/inference_pipeline/test_config_registry.py`

## Summary

M17 adds diarization as an optional helper that returns anonymous speaker-turn regions, not named product speaker labels. The pipeline still runs without diarization installed or enabled. When enabled and available, diarization turns are converted to segmentation regions before ASR; when unavailable, the pipeline records a warning and falls back to the VAD-only segmentation path.

## Runner Contract Preservation

The Evaluation Tool runner contract is unchanged. The pipeline still reads `record["inference_audio_path"]`, preserves `recording_id`, `utt_id`, `start_sec`, and `end_sec`, and returns the required `predictions/utterances.jsonl` fields: `recording_id`, `utt_id`, `start_sec`, `end_sec`, `speaker_label`, and `text`.

## Commands

- `cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_diarization_interface.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_pipeline_e2e.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_vad.py tests/inference_pipeline/test_segmentation.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest`

## Smoke Checks

- Synthetic fixed-diarizer path verifies diarization-assisted segmentation.
- Disabled config path verifies core pipeline behavior without diarization.
- Injected fake pyannote pipeline verifies anonymous speaker-turn mapping without importing or downloading pyannote assets.
- Missing pyannote path verifies optional dependency failure is reported cleanly.

## Diarization Metrics

- DER: calculable in the metric helper and covered by synthetic unit tests; not calculable on real AMI/CHiME audio in this workspace.
- JER: calculable in the metric helper and covered by synthetic unit tests; not calculable on real AMI/CHiME audio in this workspace.
- Speaker-attributed WER: not calculable in this workspace because no real diarization-assisted ASR run was executed.
- Named-speaker false assignment rate: helper added and covered by unit tests; before/after real values are not calculable without a real diarization-assisted run.
- Overlap segment detection rate: calculable in the metric helper and covered by synthetic overlap tests; not calculable on real AMI/CHiME audio in this workspace.
- Runtime and memory overhead: runtime stage diagnostics now include `diarization_sec`; real pyannote runtime and memory overhead are not available because pyannote is not installed.

## Enabled Disabled Status

Diarization is disabled by default in existing configs through `no_op_diarization`. `desktop_gpu.yaml` references `components/diarization/pyannote_community.yaml`, which is also disabled by default and has `allow_model_downloads: false`.

## Recommendation

Diarization is worth keeping only as an optional prototype helper for now. The interface, config, fallback behavior, and metrics are in place, but this workspace does not contain the required local AMI/CHiME raw audio or pyannote assets to prove material transcript improvement.

## Blockers

- `pyannote` is not installed in `/Users/billy/Documents/just-peachy/.venv`.
- Local pyannote model assets are not present under `models/cache/pyannote`.
- Raw AMI and CHiME dataset directories are not present under `Software Validation from Datasets/RawDatasets`.
- Existing M16 AMI/CHiME fixture run folders reference fixture audio paths, but fixture audio files are not materialized there.

## Incomplete

- Run a real AMI/CHiME diarization-assisted comparison after local audio, reference diarization labels, and optional pyannote assets are available.
- Populate before/after speaker-attributed WER and named-speaker false assignment rates from real predictions.
- Measure pyannote runtime and memory overhead on target hardware or a representative local machine.
