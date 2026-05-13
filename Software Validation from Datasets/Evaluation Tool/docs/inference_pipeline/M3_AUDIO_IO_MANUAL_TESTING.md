# M3 Audio IO Manual Testing Guide

This guide is for learning the M3 audio loading layer by writing and running
small experiments yourself. It does not require the Evaluation Tool GUI or a
full evaluation run.

Run commands from the Evaluation Tool root:

```powershell
cd "C:\Users\will5\Documents\just-peachy\Software Validation from Datasets\Evaluation Tool"
```

Use the project Python environment:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" --version
```

## What To Read First

Read these files in this order:

1. `app/inference_pipeline/audio_io/__init__.py`
2. `app/inference_pipeline/audio_io/loader.py`
3. `app/inference_pipeline/audio_io/segments.py`
4. `app/inference_pipeline/audio_io/multichannel.py`
5. `app/inference_pipeline/audio_io/resample.py`
6. `tests/inference_pipeline/test_audio_io.py`
7. `reports/milestones/M3_audio_io_report.md`

Key idea:

```text
record["inference_audio_path"] -> crop -> channel policy -> resample -> torch.Tensor
```

The returned tensor is channel-first:

```text
[channels, samples]
```

## Dependency Check

Before experimenting, confirm the M3 dependencies are available:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" -c "import importlib.util; print('torch', importlib.util.find_spec('torch') is not None); print('soundfile', importlib.util.find_spec('soundfile') is not None); print('scipy', importlib.util.find_spec('scipy') is not None); print('numpy', importlib.util.find_spec('numpy') is not None)"
```

Expected:

```text
torch True
soundfile True
scipy True
numpy True
```

## Generate Sample Audio

Create a scratch script named `scratch_generate_m3_audio.py` in the Evaluation
Tool root:

```python
from pathlib import Path

import numpy as np
import soundfile as sf


OUTPUT_DIR = Path("tests/fixtures/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def sine_wave(frequency_hz: float, sample_rate: int, duration_sec: float, amplitude: float) -> np.ndarray:
    sample_count = int(sample_rate * duration_sec)
    t = np.linspace(0.0, duration_sec, sample_count, endpoint=False, dtype=np.float32)
    return (amplitude * np.sin(2.0 * np.pi * frequency_hz * t)).astype(np.float32)


def write_mono_wav() -> Path:
    sample_rate = 16000
    duration_sec = 2.0
    audio = sine_wave(440.0, sample_rate, duration_sec, 0.25)
    path = OUTPUT_DIR / "manual_mono_16k.wav"
    sf.write(path, audio, sample_rate, subtype="PCM_16")
    return path


def write_stereo_wav() -> Path:
    sample_rate = 48000
    duration_sec = 3.0
    left = sine_wave(440.0, sample_rate, duration_sec, 0.25)
    right = sine_wave(880.0, sample_rate, duration_sec, 0.25)
    stereo = np.stack([left, right], axis=1)
    path = OUTPUT_DIR / "manual_stereo_48k.wav"
    sf.write(path, stereo, sample_rate, subtype="PCM_16")
    return path


if __name__ == "__main__":
    mono_path = write_mono_wav()
    stereo_path = write_stereo_wav()
    print(f"Wrote {mono_path.resolve()}")
    print(f"Wrote {stereo_path.resolve()}")
```

Run it:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" scratch_generate_m3_audio.py
```

You should now have:

```text
tests/fixtures/audio/manual_mono_16k.wav
tests/fixtures/audio/manual_stereo_48k.wav
```

## Test Default Loading

Create a scratch script named `scratch_load_default.py`:

```python
from app.inference_pipeline.audio_io import load_audio


record = {
    "recording_id": "manual-rec",
    "utt_id": "manual-utt",
    "inference_audio_path": "tests/fixtures/audio/manual_stereo_48k.wav",
}

result = load_audio(record, {})

print("waveform shape:", result.waveform.shape)
print("sample_rate:", result.sample_rate)
print("duration_sec:", result.duration_sec)
print("num_channels:", result.num_channels)
print("source_sample_rate:", result.source_sample_rate)
print("source_num_channels:", result.source_num_channels)
print("channel_policy:", result.channel_policy)
```

Run it:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" scratch_load_default.py
```

Expected learning checkpoint:

- The input file is stereo at 48 kHz.
- The output is mono at 16 kHz by default.
- A 3 second file should produce shape close to `torch.Size([1, 48000])`.

## Test Segment Cropping

Create `scratch_load_segment.py`:

```python
from app.inference_pipeline.audio_io import load_audio


record = {
    "recording_id": "manual-rec",
    "utt_id": "manual-utt-segment",
    "inference_audio_path": "tests/fixtures/audio/manual_stereo_48k.wav",
    "start_sec": 0.5,
    "end_sec": 2.0,
}

config = {
    "runtime": {"sample_rate_hz": 16000},
    "audio": {"channel_policy": "mono"},
}

result = load_audio(record, config)

print("waveform shape:", result.waveform.shape)
print("sample_rate:", result.sample_rate)
print("duration_sec:", result.duration_sec)
print("segment_start_sec:", result.segment_start_sec)
print("segment_end_sec:", result.segment_end_sec)
```

Run it:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" scratch_load_segment.py
```

Expected learning checkpoint:

- `end_sec - start_sec` is `1.5`.
- At 16 kHz, the output should have about `24000` samples.
- Shape should be close to `torch.Size([1, 24000])`.

## Test Channel Policies

Create `scratch_channel_policies.py`:

```python
from app.inference_pipeline.audio_io import load_audio


record = {
    "recording_id": "manual-rec",
    "utt_id": "manual-utt",
    "inference_audio_path": "tests/fixtures/audio/manual_stereo_48k.wav",
}

configs = {
    "mono": {
        "runtime": {"sample_rate_hz": 16000},
        "audio": {"channel_policy": "mono"},
    },
    "select_left": {
        "runtime": {"sample_rate_hz": 16000},
        "audio": {"channel_policy": "select", "channel_index": 0},
    },
    "select_right": {
        "runtime": {"sample_rate_hz": 16000},
        "audio": {"channel_policy": "select", "channel_index": 1},
    },
    "preserve": {
        "runtime": {"sample_rate_hz": 16000},
        "audio": {"channel_policy": "preserve"},
    },
}

for name, config in configs.items():
    result = load_audio(record, config)
    print()
    print(name)
    print("  waveform shape:", result.waveform.shape)
    print("  sample_rate:", result.sample_rate)
    print("  num_channels:", result.num_channels)
    print("  channel_policy:", result.channel_policy)
```

Run it:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" scratch_channel_policies.py
```

Expected learning checkpoint:

- `mono`, `select_left`, and `select_right` return one channel.
- `preserve` returns two channels.
- All outputs are channel-first.

## Test Resampling

Create `scratch_resampling.py`:

```python
from app.inference_pipeline.audio_io import load_audio


record = {
    "recording_id": "manual-rec",
    "utt_id": "manual-utt",
    "inference_audio_path": "tests/fixtures/audio/manual_stereo_48k.wav",
}

for target_sample_rate in [8000, 16000, 24000, 48000]:
    result = load_audio(
        record,
        {
            "runtime": {"sample_rate_hz": target_sample_rate},
            "audio": {"channel_policy": "mono"},
        },
    )
    print(target_sample_rate, result.waveform.shape, result.duration_sec)
```

Run it:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" scratch_resampling.py
```

Expected learning checkpoint:

- The output sample rate should match the target.
- The sample count should change with sample rate.
- The duration should stay close to 3 seconds.

## Test Failure Cases

Create `scratch_failure_cases.py`:

```python
from app.inference_pipeline.audio_io import load_audio


valid_path = "tests/fixtures/audio/manual_stereo_48k.wav"

cases = {
    "missing inference_audio_path": {
        "record": {"recording_id": "rec", "utt_id": "utt"},
        "config": {},
    },
    "missing file": {
        "record": {
            "recording_id": "rec",
            "utt_id": "utt",
            "inference_audio_path": "tests/fixtures/audio/does_not_exist.wav",
        },
        "config": {},
    },
    "negative start": {
        "record": {
            "recording_id": "rec",
            "utt_id": "utt",
            "inference_audio_path": valid_path,
            "start_sec": -1.0,
            "end_sec": 1.0,
        },
        "config": {},
    },
    "end before start": {
        "record": {
            "recording_id": "rec",
            "utt_id": "utt",
            "inference_audio_path": valid_path,
            "start_sec": 2.0,
            "end_sec": 1.0,
        },
        "config": {},
    },
    "bad channel policy": {
        "record": {
            "recording_id": "rec",
            "utt_id": "utt",
            "inference_audio_path": valid_path,
        },
        "config": {"audio": {"channel_policy": "bad_policy"}},
    },
    "bad channel index": {
        "record": {
            "recording_id": "rec",
            "utt_id": "utt",
            "inference_audio_path": valid_path,
        },
        "config": {"audio": {"channel_policy": "select", "channel_index": 99}},
    },
}

for name, payload in cases.items():
    try:
        load_audio(payload["record"], payload["config"])
    except Exception as exc:
        print(f"{name}: {type(exc).__name__}: {exc}")
    else:
        print(f"{name}: unexpectedly succeeded")
```

Run it:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" scratch_failure_cases.py
```

Expected learning checkpoint:

- Every case should fail clearly.
- Most validation failures should be `ContractValidationError` or
  `MissingRequiredFieldError`.
- Missing files should raise `FileNotFoundError`.

## Test The Evaluator Path Rule

Create `scratch_inference_path_wins.py`:

```python
from app.inference_pipeline.audio_io import load_audio


record = {
    "recording_id": "manual-rec",
    "utt_id": "manual-utt",
    "inference_audio_path": "tests/fixtures/audio/manual_mono_16k.wav",
    "audio_path_resolved": "tests/fixtures/audio/this_file_should_not_be_used.wav",
}

result = load_audio(record, {"runtime": {"sample_rate_hz": 16000}})

print("loaded path:", result.audio_path)
print("waveform shape:", result.waveform.shape)
print("sample_rate:", result.sample_rate)
```

Run it:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" scratch_inference_path_wins.py
```

Expected learning checkpoint:

- Loading should succeed.
- `result.audio_path` should be `manual_mono_16k.wav`.
- This proves M3 honors `inference_audio_path` and ignores
  `audio_path_resolved`.

## Run The Focused M3 Test

After experimenting, run the official focused test:

```powershell
& "C:\Users\will5\Documents\just-peachy\myenv\Scripts\python.exe" -m pytest tests\inference_pipeline\test_audio_io.py
```

Expected:

```text
17 passed
```

## Understanding Checkpoints

You understand M3 when you can explain:

- Why `record["inference_audio_path"]` must be used instead of source paths.
- Why the output tensor is channel-first.
- Why segment cropping happens before resampling.
- How output sample count relates to duration and target sample rate.
- Why mono/select/preserve channel policies produce different tensor shapes.
- Which failures should happen before downstream ASR or model code ever runs.

## Cleanup

The sample WAVs and scratch scripts are optional. You can delete them when you
are done:

```powershell
Remove-Item scratch_generate_m3_audio.py
Remove-Item scratch_load_default.py
Remove-Item scratch_load_segment.py
Remove-Item scratch_channel_policies.py
Remove-Item scratch_resampling.py
Remove-Item scratch_failure_cases.py
Remove-Item scratch_inference_path_wins.py
Remove-Item tests\fixtures\audio\manual_mono_16k.wav
Remove-Item tests\fixtures\audio\manual_stereo_48k.wav
```
