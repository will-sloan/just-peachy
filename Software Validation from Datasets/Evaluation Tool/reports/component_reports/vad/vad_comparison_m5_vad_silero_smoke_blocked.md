# VAD Component Report

## Milestone

M5 - VAD Interface and First VAD Adapter

- Run id: `m5_vad_silero_smoke_blocked`
- Selected VAD backend: `silero_vad`
- Silero status: available locally. The active venv can import `silero_vad`,
  `onnxruntime`, and `torchaudio`, and the focused test loaded the packaged
  Silero JIT model through `silero_vad.load_silero_vad()` without downloading
  assets.

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
- `reports/component_reports/vad/vad_comparison_m5_vad_silero_smoke_blocked.md`

## Summary

M5 adds a swappable `VADBase` interface that returns existing
`SpeechRegion` objects. The working primary backend is now `SileroVAD`, loaded
from the locally installed `silero_vad` package assets. The deterministic
`EnergyVAD` backend remains available as an offline fallback and test baseline.

The Silero adapter is lazy: selecting the component by config does not import
or load the model. The packaged model is loaded only when `detect()` runs.
Silero timestamp output is converted to `SpeechRegion` rows with `start_sec`,
`end_sec`, `label="speech"`, and `confidence=None` because the Silero timestamp
API used here does not expose per-region confidence.

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

Dependency result:

```text
torch True
torchaudio True
silero True
silero_vad True
onnxruntime True
numpy True
pytest True
```

Compile check:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m compileall app/inference_pipeline/vad tests/inference_pipeline/test_vad.py
```

Focused tests:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_vad.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py
```

Test results:

```text
tests/inference_pipeline/test_vad.py: 13 passed, 1 warning
tests/inference_pipeline/test_config_registry.py: 10 passed
tests/model_runner/test_external_stub_bridge.py: 4 passed
```

The warning is from PyTorch while loading Silero's packaged JIT model on
Python 3.14:

```text
torch.jit.load is not supported in Python 3.14+ and may break.
```

Smoke commands:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --dataset cmu_arctic --max-recordings 1 --runner external-stub --run-name m5_vad_silero_smoke
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --project-root /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets --dataset cmu_arctic --max-recordings 1 --runner external-stub --run-name m5_vad_silero_smoke
```

Smoke result:

```text
ERROR: Could not find project root. Run from inside the project, or pass --project-root.
```

No run folder was created for `m5_vad_silero_smoke`.

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
- `EnergyVAD` confidence is populated;
- `SileroVAD` confidence is `None` because the timestamp API does not provide it;
- `energy_vad` and `silero_vad` can be selected by config;
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

## Incomplete

- No dataset smoke VAD report was generated because the Evaluation Tool smoke
  command is blocked before run creation.
- ASR, speaker diarization, speaker embeddings, model adapters beyond VAD,
  Raspberry Pi optimization, ExecuTorch export, and hardware acceleration remain
  intentionally out of scope for M5.
