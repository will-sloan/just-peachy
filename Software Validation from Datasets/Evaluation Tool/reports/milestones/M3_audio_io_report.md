# M3 Audio IO Report

## Summary

M3 added a PyTorch-native audio input layer under
`app/inference_pipeline/audio_io/`. The new loader reads one Evaluation Tool
metadata row at a time, uses `record["inference_audio_path"]` as the only audio
source, applies optional `start_sec`/`end_sec` cropping, resamples to the
configured target sample rate, and returns a channel-first `torch.Tensor`.

Changed files:

- `app/inference_pipeline/audio_io/__init__.py`
- `app/inference_pipeline/audio_io/loader.py`
- `app/inference_pipeline/audio_io/segments.py`
- `app/inference_pipeline/audio_io/resample.py`
- `app/inference_pipeline/audio_io/multichannel.py`
- `tests/inference_pipeline/test_audio_io.py`
- `tests/fixtures/audio/.gitkeep`
- `docs/inference_pipeline/MILESTONE_LEDGER.md`
- `reports/milestones/M3_audio_io_report.md`

## Public API

`app.inference_pipeline.audio_io` exports:

- `load_audio(record, config)`
- `LoadedAudio`

`LoadedAudio` includes the model-ready waveform tensor, output sample rate,
duration, output channel count, JSON-safe channel policy metadata, source sample
rate, source channel count, source duration, segment start/end fields, and the
resolved `inference_audio_path`.

## Inference Audio Path Rule

`load_audio` requires `record["inference_audio_path"]`. It does not fall back to
`audio_path_resolved`, even when that field is present. The focused tests include
a row where `audio_path_resolved` points to a missing file while
`inference_audio_path` points to a valid fixture; loading succeeds from
`inference_audio_path`.

## Segment Cropping

`segments.py` validates optional timestamps and converts them to source sample
frames before resampling. Invalid values fail with `ContractValidationError`:

- non-numeric timestamps
- negative `start_sec` or `end_sec`
- `end_sec <= start_sec`
- requested start/end positions beyond the source file
- empty segments

When both timestamps are present, the returned duration is checked against the
loaded output tensor duration after resampling.

## Resampling

`resample.py` uses `scipy.signal.resample_poly` with a GCD-reduced up/down ratio.
If the source and target sample rates match, it returns float32 audio without
copying when possible. Target sample rate resolution supports dict configs and
`PipelineConfig`:

- `config["audio"]["target_sample_rate_hz"]`
- `config["audio"]["sample_rate_hz"]`
- `config.runtime.sample_rate_hz`
- `config["runtime"]["sample_rate_hz"]`
- `config["sample_rate_hz"]`
- default `16000`

## Channel Policies

`multichannel.py` supports:

- `mono`: downmixes all channels to one channel
- `select`: selects one configured or record-provided `channel_index`
- `preserve`: preserves all source channels

Output tensors are channel-first:

- mono/select: `[1, samples]`
- preserve: `[channels, samples]`

Channel policy metadata is JSON-safe and records the canonical policy,
source channel count, output channel count, and selected channel index where
applicable.

## Dependency Check

The project `myenv` was checked before implementation. `torch`, `soundfile`,
`scipy`, and `numpy` were importable. `torchaudio` was not importable, so M3 uses
the planned `soundfile`/`scipy` path and returns `torch.Tensor`.

Exact dependency check command run from the Evaluation Tool root:

```powershell
& 'C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe' -c "import importlib.util; print('torch', importlib.util.find_spec('torch') is not None); print('torchaudio', importlib.util.find_spec('torchaudio') is not None); print('soundfile', importlib.util.find_spec('soundfile') is not None); print('scipy', importlib.util.find_spec('scipy') is not None); print('numpy', importlib.util.find_spec('numpy') is not None)"
```

Observed result:

```text
torch True
torchaudio False
soundfile True
scipy True
numpy True
```

## Validation Commands

Run from `Software Validation from Datasets\Evaluation Tool`:

```powershell
& 'C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe' -m pytest tests\inference_pipeline\test_audio_io.py
& 'C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe' -m pytest tests\inference_pipeline\test_contracts.py
& 'C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe' -m pytest tests\inference_pipeline\test_config_registry.py
& 'C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe' -m pytest tests\test_m0_docs.py
```

## Test Results

- `tests\inference_pipeline\test_audio_io.py`: 17 passed.
- `tests\inference_pipeline\test_contracts.py`: 11 passed.
- `tests\inference_pipeline\test_config_registry.py`: 10 passed.
- `tests\test_m0_docs.py`: 5 passed.

## Known Limitations

- M3 does not wire audio loading into `ExternalStubRunner`; it only adds the
  callable audio input layer for future inference code.
- M3 does not add VAD, ASR, diarization, speaker embedding, model loading,
  Raspberry Pi optimization, ExecuTorch export, or hardware-specific logic.
- `torchaudio` is not available in the current environment, so audio file IO and
  resampling use `soundfile` and `scipy` while returning `torch.Tensor`.

## Protected-Path Safety Confirmation

No M3 edits were made to:

- `app/model_runner/`
- `app/prediction_io/`
- `app/scoring/`
- `app/dataset_registry/`
- `app/gui/`
- `app/cli/`
- `app/plotting/`
- `app/reporting/`
- normalized metadata loaders

## Open Issues

None known.
