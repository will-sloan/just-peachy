# ASR Pipeline Setup and Architecture

> **Historical document.** This file describes the pre-automation pipeline handoff.
> For the accepted current architecture and operating procedures, use
> `Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/current_evaluation_tool_architecture.md`
> and `system_guide.md`. The final acceptance audit is authoritative when this
> historical text disagrees with current behavior.

This guide documents the repository as it exists on Windows after a verified
local run. It covers installation and the existing examples/tests only. It does
not change the ASR pipeline or implement evaluation-tool integration.

## Scope and intended environment

The active implementation is the modular inference pipeline inside:

```text
Software Validation from Datasets/Evaluation Tool/app/inference_pipeline/
```

The currently validated desktop environment is Windows with Python 3.12. The
installer accepts Python 3.10, 3.11, and 3.12. Python 3.13+ is not accepted by
`install.ps1`; Python 3.14 was present in the original `.venv` and was repaired
by moving it to a timestamped `.venv.broken.*` backup and creating a Python 3.12
environment.

The default validated realtime path is CPU-only:

```text
16 kHz audio
Whisper base ASR, English, beam size 1
SpeechBrain ECAPA speaker embedding, 192 dimensions
Cosine centroid speaker matching, threshold 0.70
No-op VAD, no-op segmentation, no-op diarization
Implicit model downloads disabled
```

CUDA is optional. Selecting a CUDA runtime alone does not move Whisper to the
GPU; the runtime and ASR component must both be configured for CUDA/float16.

## Installation sequence

Run these commands from the repository root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1 -Profile inference -InstallFFmpeg
```

The `inference` profile installs the core packages plus PyTorch, torchaudio,
OpenAI Whisper, SpeechBrain, Silero VAD, and sounddevice. `-InstallFFmpeg`
installs FFmpeg through WinGet if it is not already on `PATH`.

The `full` profile additionally installs the optional Faster-Whisper,
pyannote, Sherpa-ONNX, Vosk, and WeNet packages. Their model weights remain a
separate, explicit installation step.

For development and tests, install the additional development tools:

```powershell
.\install.ps1 -Profile dev
```

The installer creates or reuses `.venv`. If the existing environment points at
a missing or unsupported Python installation, it moves the environment to a
timestamped `.venv.broken.<timestamp>` directory before recreating it; it does
not delete that backup. Installation transcripts are written to
`.install-logs/`.

Do not rely on an activated shell. The explicit interpreter is unambiguous:

```powershell
.\.venv\Scripts\python.exe --version
```

Expected result is Python 3.10–3.12; the verified environment used Python
3.12.7.

## Model assets

Package installation and model downloads are separate. The default cache is:

```text
models/cache/whisper/<model>.pt
models/cache/faster_whisper/tiny/
models/cache/speechbrain/spkrec-ecapa-voxceleb/
models/cache/pyannote/
```

Bootstrap the assets used by the validated realtime path with:

```powershell
.\.venv\Scripts\python.exe scripts\bootstrap_models.py `
  --whisper base `
  --speechbrain-ecapa `
  --silero
```

The permitted OpenAI Whisper sizes are `tiny`, `base`, and `small`. This policy
is enforced both by the component registry and by the OpenAI/Faster-Whisper
runtime adapters before model loading. The adapters pass cropped, mono 16 kHz
waveforms in memory, so normal WAV inference does not rely on an ambient
FFmpeg executable and always honors record/segment bounds.

Pyannote is optional and not part of the validated default path. It may require
accepting gated Hugging Face model terms and a token:

```powershell
$env:HF_TOKEN = "your-token"
.\.venv\Scripts\python.exe scripts\bootstrap_models.py --pyannote
```

Never commit tokens to YAML, scripts, logs, or this guide. The pyannote
component configuration names `PYANNOTE_AUTH_TOKEN` as its runtime token
environment variable; use the variable expected by the specific command or
configuration being run.

## Verification checkpoints

After package installation and model bootstrap, run:

```powershell
.\.venv\Scripts\python.exe scripts\verify_install.py `
  --profile inference `
  --device cpu `
  --require-models `
  --whisper base
```

This checks imports, FFmpeg, CUDA status, Whisper cache files, SpeechBrain
markers, and resolution of the real realtime configuration. A successful CPU
check reports CUDA as `SKIP` and all required checks as `PASS`.

For the development profile, the equivalent check is:

```powershell
.\.venv\Scripts\python.exe scripts\verify_install.py `
  --profile dev `
  --device cpu `
  --require-models `
  --whisper base
```

## Run the existing realtime example

Change to the Evaluation Tool directory:

```powershell
cd "Software Validation from Datasets\Evaluation Tool"
```

Run the included prerecorded WAV through the realtime windowing path:

```powershell
..\..\.venv\Scripts\python.exe scripts\live_mic_realtime.py `
  --config configs\inference\live_mic_realtime_whisper_base_speaker_matching.yaml `
  --run-id my_realtime_run `
  --input-wav artifacts\realtime_test_audio\aew_alt_rxr_eey_random_30s.wav `
  --duration-sec 32.2 `
  --window-sec 3.0 `
  --hop-sec 3.0 `
  --sample-rate 16000 `
  --recording-id my_realtime_run
```

Inputs are a WAV path, a unique run id, a recording id, and realtime window
settings. Use a new run id for each experiment.

Outputs are written below:

```text
runs/live_mic_realtime/<run-id>/
  summary.json
  predictions/utterances.jsonl
  predictions/diagnostics.jsonl
```

The required utterance JSONL fields are `recording_id`, `utt_id`, `start_sec`,
`end_sec`, `speaker_label`, and `text`. The diagnostics include stage timings,
model ids, realtime factor, queue/drop information, transcript details, and
speaker decisions. A component report is also written under
`reports/component_reports/live_mic_realtime/`.

The same script can capture from a microphone by omitting `--input-wav`; that
path requires a working sounddevice input device and is not covered by the
prerecorded validation above.

## Run tests and the component sweep

From the Evaluation Tool directory:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests -q
```

The verified repository-wide result was 189 passed, with two non-fatal
dependency deprecation warnings from Silero/Torch serialization.

Preview the default realtime component matrix without loading models:

```powershell
..\..\.venv\Scripts\python.exe scripts\run_realtime_component_sweep.py `
  --run-id preview `
  --dry-run
```

The default enabled matrix expands to 48 cases. A small real smoke is:

```powershell
..\..\.venv\Scripts\python.exe scripts\run_realtime_component_sweep.py `
  --run-id base_smoke `
  --models base `
  --max-cases 2
```

Sweep output includes a manifest, generated configs, logs, per-case summaries,
checkpointed `results.jsonl`, and consolidated `results.csv` under
`runs/realtime_component_sweeps/<run-id>/`. Downloads remain disabled unless
`--allow-model-downloads` is passed.

## Architecture and data flow

The main entry point is `PipelineRunner.from_config_path()` in
`app/inference_pipeline/pipeline.py`. YAML is parsed by
`app/inference_pipeline/config.py`, and component names/adapters are resolved by
`app/inference_pipeline/registry.py`.

For one selected record, the normal flow is:

```text
EvaluationRecord
  -> audio_io.load_audio (load, mono conversion, resampling)
  -> VAD, if enabled
  -> segmentation, if enabled
  -> diarization, if enabled
  -> ASR for each resulting segment
  -> speaker embedding, if enabled
  -> enrolled-speaker matcher, if enabled
  -> transcript assembly and runtime diagnostics
  -> PipelineOutput / utterance prediction row
```

`PipelineRunner` preserves `recording_id`, `utt_id`, timing fields, and speaker
labels through the contracts in `app/inference_pipeline/contracts.py`. The
Evaluation Tool owns dataset selection, augmentation, run folders, scoring,
plots, and reports; the inference package supplies predictions and diagnostics.

### Components and configuration

The validated configuration is:

```text
configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml
```

Its reusable component references and responsibilities are:

| Stage | Config/implementation | Current role |
|---|---|---|
| Audio | `audio_io/loader.py` | Reads the input path and prepares 16 kHz model audio |
| VAD | inline `no_op_vad` | Disabled in the validated config |
| Segmentation | inline `no_op_segmentation` | Disabled; the full window is sent to ASR |
| Diarization | inline `no_op_diarization` | Disabled |
| ASR | `components/asr/whisper_base.yaml`, `asr/whisper_adapter.py` | OpenAI Whisper base, English, CPU, float32 |
| Embedding | `components/speaker_embedding/speechbrain_ecapa.yaml` | SpeechBrain ECAPA, 192-dimensional embedding |
| Matching | inline `cosine_threshold` | Centroid cosine score, threshold 0.70, `Unknown` fallback |
| Assembly | `transcript/assembler.py` | Builds final transcript spans and diagnostics |

Model loading is lazy: resolving a configuration does not load every model.
Whisper and SpeechBrain load on the first inference call. This is why the first
realtime window is normally much slower than later windows.

The enrollment database used by the validated config is:

```text
artifacts/enrollment/enrollment_db_speechbrain_ecapa.json
```

It currently contains one enrolled speaker, Alice. With one speaker there is no
meaningful second-best score or `min_margin` rejection; add a second speaker
before interpreting margin behavior.

## Other registered paths and limitations

- OpenAI Whisper Tiny, Base, and Small have component YAML and registry entries.
- Faster-Whisper has an executable, lazy-loaded adapter and a reusable Tiny
  component YAML. It consumes in-memory 16 kHz segments, exhausts the backend's
  generator, preserves word timings, and refuses implicit downloads by default.
- Sherpa-ONNX, Vosk, and WeNet have executable, lazy-loaded ASR adapters and
  reusable component YAML files. They require explicitly configured local model
  assets; WeNet downloads only when `allow_model_downloads` is deliberately set.
- Energy VAD and Silero VAD are available; both are opt-in configurations.
- VAD-region segmentation is available as an opt-in component.
- Pyannote community diarization is optional, token-dependent, and disabled by
  default. Its anonymous turns (for example `speaker_00`) are separate from
  enrolled-speaker matching.
- The realtime sweep records latency, realtime factor, stage timing, queue drops,
  and speaker decisions. It does not automatically compute WER for the realtime
  WAV without separately supplied reference text.
- The dependency files contain package names rather than a fully pinned lock
  file, so a clean-machine install should be validated before claiming exact
  reproducibility.

## Troubleshooting

### The venv points at a missing or unsupported Python

Use the installer with an explicit rebuild:

```powershell
.\install.ps1 -Profile inference -ForceRecreateVenv
```

The old environment is moved to a timestamped backup. Ensure `py -3.12` or a
Python 3.12 executable is installed.

### `WinError 2` or FFmpeg errors

Check:

```powershell
where.exe ffmpeg
ffmpeg -version
```

If missing, reopen PowerShell after:

```powershell
.\install.ps1 -Profile inference -InstallFFmpeg
```

### Model asset missing

The configs deliberately disable implicit downloads. Run `bootstrap_models.py`
for the exact model/component, then rerun `verify_install.py` with
`--require-models`.

### SpeechBrain symlink warning or privilege error

The project uses SpeechBrain's copy strategy on Windows. The warning about the
Hugging Face cache using symlinks is informational; the project cache should
still contain `hyperparams.yaml` and checkpoint files. Re-run the bootstrap if
the project cache is incomplete.

### CUDA is available but execution uses CPU

This is controlled by configuration. Set both the runtime device/precision and
the ASR component device/dtype, or select the sweep's `cuda_fp16` profile.

### Realtime queue drops or unexpectedly high first latency

Separate first-load latency from steady state. Pre-bootstrap assets, increase
`--max-queue`, and compare `drop_oldest`, `drop_newest`, and `block` policies.

## Future evaluation integration boundary

Integration is intentionally not implemented in this setup task. The existing
Evaluation Tool contract is the safe boundary for future work:

```text
record["inference_audio_path"]
  -> model runner / PipelineRunner
  -> predictions/utterances.jsonl
  -> existing scorer, metrics, plots, and reports
```

The model must read `inference_audio_path`, preserve `recording_id` and `utt_id`,
and return the required prediction fields. This allows future combinations of
ASR, VAD, segmentation, diarization, embedding, and matching components to be
benchmarked for accuracy, latency, memory, and throughput without changing
dataset selection or scoring behavior.
