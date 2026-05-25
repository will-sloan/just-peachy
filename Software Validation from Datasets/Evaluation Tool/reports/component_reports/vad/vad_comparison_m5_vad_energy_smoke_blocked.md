# VAD Component Report

> Superseded by `vad_comparison_m5_vad_silero_smoke_blocked.md` after
> `silero_vad`, `onnxruntime`, and `torchaudio` were installed locally.

## Milestone

M5 - VAD Interface and First VAD Adapter

- Run id: `m5_vad_energy_smoke_blocked`
- Selected VAD backend: `energy_vad`
- Silero status: blocked locally. Dependency check showed `silero`, `silero_vad`,
  `onnxruntime`, and `torchaudio` are not importable in the active venv, so M5
  uses the deterministic energy baseline and keeps Silero as a lazy adapter
  boundary.

## Files Changed

- `app/inference_pipeline/vad/__init__.py`
- `app/inference_pipeline/vad/base.py`
- `app/inference_pipeline/vad/silero_vad.py`
- `app/inference_pipeline/vad/energy_vad.py`
- `app/inference_pipeline/vad/report.py`
- `app/inference_pipeline/pipeline.py`
- `app/inference_pipeline/registry.py`
- `configs/inference/components/vad/silero.yaml`
- `configs/inference/components/vad/energy.yaml`
- `tests/inference_pipeline/test_vad.py`
- `reports/component_reports/vad/vad_comparison_m5_vad_energy_smoke_blocked.md`

## Summary

M5 adds a swappable `VADBase` interface that returns existing
`SpeechRegion` objects. The working backend is `EnergyVAD`, a deterministic
frame-RMS detector that exposes `threshold`, `min_speech_ms`,
`min_silence_ms`, `pad_ms`, and `sample_rate` parameters.

The Silero adapter is present only as a lazy boundary. It does not import,
download, or load model assets during module import. Selecting it without local
assets raises a clear unavailable-model error.

The M4 pipeline skeleton can now run with VAD enabled or disabled. When enabled,
the pipeline records `vad_sec` and `vad_region_count` in `RuntimeStats`; it does
not change prediction identity or the required utterance JSONL schema.

## Runner Contract Preservation

- `ExternalStubRunner.predict_one(record, run_config, logger)` still returns the
  existing `UtterancePrediction` type.
- The pipeline still receives one selected metadata row at a time.
- `record["inference_audio_path"]` remains the audio source.
- `recording_id`, `utt_id`, `start_sec`, and `end_sec` are preserved.
- `predictions/utterances.jsonl` remains owned by `ModelRunner.run_batch()`.
- No scorer, plot generation, report generator, GUI, CLI, dataset registry, or
  normalized metadata behavior was redesigned.

## Commands

Dependency check:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -c "import importlib.util; names=['torch','torchaudio','silero','silero_vad','onnxruntime','numpy','pytest']; print('\n'.join(f'{name} {importlib.util.find_spec(name) is not None}' for name in names))"
```

Focused tests:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_vad.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py
```

Test results:

```text
tests/inference_pipeline/test_vad.py: 10 passed
tests/inference_pipeline/test_config_registry.py: 10 passed
tests/model_runner/test_external_stub_bridge.py: 4 passed
```

Smoke commands:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --dataset cmu_arctic --max-recordings 1 --runner external-stub --run-name m5_vad_energy_smoke
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --project-root /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets --dataset cmu_arctic --max-recordings 1 --runner external-stub --run-name m5_vad_energy_smoke
```

Smoke result:

```text
ERROR: Could not find project root. Run from inside the project, or pass --project-root.
```

## VAD Metrics And Validation Results

The CLI smoke command failed before a run folder was created, so no dataset VAD
metrics were produced from a smoke run.

Focused tests validated these metric calculations with synthetic regions:

- Speech coverage ratio: `0.6000`
- Region count: `2`
- Segment count per minute: `120.0000`
- VAD runtime real-time factor: `0.0200`
- False speech rate with reference regions: `0.4000`
- Missed speech rate with reference regions: `0.2000`
- Boundary error with reference regions: `0.0500 sec`

Focused tests also validated:

- silence returns no regions;
- one speech region is detected;
- multiple speech regions are detected;
- very short audio is handled safely;
- returned objects are `SpeechRegion` instances with valid ordered timestamps;
- confidence is produced by `EnergyVAD`;
- `energy_vad` can be selected by config;
- disabled/no-op VAD remains supported;
- the pipeline runs with VAD enabled and disabled.

## Enabled Disabled Status

The focused pipeline test confirms enabled VAD records `vad_sec` and
`vad_region_count`, while disabled VAD leaves those runtime fields unset. The
prediction row contract is unchanged in both paths.

## Blockers

- The local project root is missing `Raw Datasets (Not formatted)`.
  `app.utils.paths.find_project_root()` requires both `Normalized Metadata` and
  `Raw Datasets (Not formatted)`, so the Evaluation Tool smoke command fails
  before dataset selection, VAD, inference, scoring, plotting, or reporting.
  Retrying with explicit `--project-root` fails for the same anchor check.
- Silero dependencies/model assets are not locally available.

## Incomplete

- No Silero-backed VAD execution was implemented because local dependencies and
  model assets are unavailable.
- No dataset smoke VAD report was generated because the Evaluation Tool smoke
  command is blocked before run creation.
- ASR, speaker diarization, speaker embeddings, model adapters beyond VAD,
  Raspberry Pi optimization, ExecuTorch export, and hardware acceleration remain
  intentionally out of scope for M5.
