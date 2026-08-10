# just-peachy

Local speech-pipeline validation for ASR, voice activity detection, speaker
embeddings, enrolled-speaker matching, diarization experiments, and
dataset-aware evaluation. The repository includes prerecorded realtime
simulation, microphone capture, component sweeps, enrollment tooling, and
performance reports.

The currently validated desktop path is Windows with Python 3.12. Python
3.10-3.12 is accepted by the installer.

## Quick Start

Open PowerShell in the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
./install.ps1 -Profile inference -InstallFFmpeg -DownloadModels
```

The installer creates `.venv`, installs the local inference stack, downloads
Whisper base plus SpeechBrain ECAPA and Silero assets, and runs verification.
It does not require activation, but the environment can be activated with:

```powershell
./.venv/Scripts/Activate.ps1
```

Run the prerecorded realtime example:

```powershell
cd "Software Validation from Datasets/Evaluation Tool"

../../.venv/Scripts/python.exe scripts/live_mic_realtime.py `
  --config configs/inference/live_mic_realtime_whisper_base_speaker_matching.yaml `
  --run-id first_run `
  --input-wav artifacts/realtime_test_audio/aew_alt_rxr_eey_random_30s.wav `
  --duration-sec 32.2 `
  --window-sec 3.0 `
  --hop-sec 3.0 `
  --sample-rate 16000 `
  --recording-id first_run
```

Run artifacts are written below `Evaluation Tool/runs/`.

## Installation Profiles

| Profile | Contents |
|---|---|
| `core` | Dataset loading, audio processing, metrics, plots, and reports |
| `inference` | Core plus PyTorch, OpenAI Whisper, SpeechBrain, Silero, and microphone capture |
| `full` | Inference plus Faster-Whisper, pyannote, Sherpa-ONNX, Vosk, and WeNet packages |
| `dev` | Inference plus pytest, coverage, Ruff, and mypy |

Examples:

```powershell
./install.ps1 -Profile core
./install.ps1 -Profile inference -InstallFFmpeg
./install.ps1 -Profile full -Device cuda
./install.ps1 -Profile dev
```

Useful installer options:

- `-Python C:/path/to/python.exe` selects a specific interpreter.
- `-ForceRecreateVenv` backs up the existing `.venv` and creates a new one.
- `-InstallFFmpeg` installs FFmpeg through WinGet when it is missing.
- `-DownloadModels` downloads the default local model assets.
- `-WhisperModels tiny,base,small` selects Whisper checkpoints to cache.
- `-Device cpu|cuda|auto` controls installation verification expectations.

If `.venv` is broken, the installer moves it to
`.venv.broken.<timestamp>` before recreating it. It does not delete the old
environment. Installer transcripts are saved under `.install-logs/`.

## Dependency Layout

The root `requirements.txt` installs the standard inference profile.
Individual profiles are available under `requirements/`:

```text
requirements/
  core.txt
  inference.txt
  optional.txt
  dev.txt
```

The legacy Evaluation Tool requirements entry point delegates to
`requirements/core.txt`, so existing commands remain valid.

## Model Assets

Model downloads are deliberately separate from package installation. Cache
locations are:

```text
models/cache/whisper/
models/cache/faster_whisper/tiny/
models/cache/speechbrain/spkrec-ecapa-voxceleb/
models/cache/pyannote/
```

Download selected assets manually:

```powershell
./.venv/Scripts/python.exe scripts/bootstrap_models.py `
  --whisper tiny,base,small `
  --speechbrain-ecapa `
  --silero
```

Available OpenAI Whisper configurations are restricted to `tiny`, `base`, and
`small`. The registry and both Whisper runtime adapters enforce this allowlist
before loading a model.

Four additional ASR adapters are available in the `full` installation:

| Component | Configuration | Expected local assets |
|---|---|---|
| Faster-Whisper Tiny | `components/asr/faster_whisper.yaml` | A local CTranslate2 Tiny model directory |
| Sherpa-ONNX | `components/asr/sherpa_onnx.yaml` | `tokens.txt` plus streaming transducer `encoder.onnx`, `decoder.onnx`, and `joiner.onnx` |
| Vosk | `components/asr/vosk.yaml` | An extracted Vosk model directory |
| WeNet | `components/asr/wenet.yaml` | A WeNet checkpoint directory containing the runtime-required `final.zip` and `units.txt` |

The example configurations look under `models/cache/<backend>/asr`. Model
downloads are not automatic; update the paths in the component YAML when the
downloaded artifact uses different filenames.

Pyannote is optional and its model requires the owner to accept the Community-1
model terms and provide a Hugging Face token through the project-approved
variable. The acknowledgement variable records that the owner performed the
licence action; it is not a substitute for accepting the terms on Hugging Face.

```powershell
$env:PYANNOTE_LICENSE_ACCEPTED = "yes"
$pyannoteSecureToken = Read-Host -AsSecureString "Hugging Face token"
$pyannoteTokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pyannoteSecureToken)
try {
  $env:PYANNOTE_AUTH_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pyannoteTokenPointer)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pyannoteTokenPointer)
}
./.venv/Scripts/python.exe scripts/bootstrap_models.py `
  --pyannote `
  --hf-token-env PYANNOTE_AUTH_TOKEN
```

Do not place tokens in YAML files, commands committed to Git, or installation
logs.

## Verify an Existing Installation

```powershell
./.venv/Scripts/python.exe scripts/verify_install.py `
  --profile inference `
  --device auto `
  --require-models `
  --whisper base
```

Verification checks Python imports, FFmpeg, CUDA availability, model-cache
markers, and resolution of the real pipeline configuration.

## Speaker Enrollment

From `Software Validation from Datasets/Evaluation Tool`:

```powershell
../../.venv/Scripts/python.exe scripts/enroll_speaker.py `
  --display-name Alice `
  --audio path/to/alice_01.wav path/to/alice_02.wav `
  --model-id speechbrain_ecapa `
  --backend speechbrain
```

Enrollment data defaults to
`artifacts/enrollment/enrollment_db_speechbrain_ecapa.json`.

## Component Performance Sweep

Preview the matrix without loading models:

```powershell
../../.venv/Scripts/python.exe scripts/run_realtime_component_sweep.py `
  --run-id preview `
  --dry-run
```

Run a small base-model smoke:

```powershell
../../.venv/Scripts/python.exe scripts/run_realtime_component_sweep.py `
  --run-id base_smoke `
  --models base `
  --max-cases 2
```

Run or resume the enabled matrix:

```powershell
../../.venv/Scripts/python.exe scripts/run_realtime_component_sweep.py --run-id full_matrix
../../.venv/Scripts/python.exe scripts/run_realtime_component_sweep.py --run-id full_matrix --resume
```

Each case records generated configuration, console output, prediction count,
latency, ASR real-time factor, stage timings, queue drops, speaker scores, and
acceptance counts. Consolidated results are written as `results.jsonl` and
`results.csv`.

## CPU and CUDA

The default realtime configuration uses CPU even when CUDA is available. To
test CUDA, both the pipeline runtime and ASR component must select `cuda` and
`float16`. The component sweep provides a `cuda_fp16` device profile:

```powershell
../../.venv/Scripts/python.exe scripts/run_realtime_component_sweep.py `
  --run-id turbo_cuda `
  --models turbo `
  --devices cuda_fp16 `
  --allow-model-downloads
```

`install.ps1 -Device cuda` verifies that the installed PyTorch build can see
the GPU. It does not silently replace PyTorch with a different CUDA wheel.

## Troubleshooting

### Virtual environment cannot create a process

The environment points to a Python installation that was moved or removed.
Run:

```powershell
./install.ps1 -Profile inference -ForceRecreateVenv
```

The existing environment is retained as a timestamped backup.

### `WinError 2` during Whisper transcription

Whisper could not find FFmpeg. Check:

```powershell
where.exe ffmpeg
ffmpeg -version
```

Install it with:

```powershell
./install.ps1 -Profile inference -InstallFFmpeg
```

Reopen PowerShell if a newly installed executable is not visible.

### Whisper or SpeechBrain assets are unavailable

The pipeline disables implicit downloads by default. Run the model bootstrap
helper or temporarily enable downloads in the relevant experiment config.

### SpeechBrain symlink privilege error on Windows

The project adapter and bootstrap helper use SpeechBrain's copy strategy, so
Administrator mode and Windows Developer Mode are not required. Make sure the
repository changes are current and rerun model bootstrap.

### CUDA is available but Whisper runs on CPU

This is a configuration choice, not an installation failure. Select the CUDA
runtime and ASR component or use the sweep's `cuda_fp16` profile.

### Hugging Face rate-limit warning

Unauthenticated public downloads still work with lower limits. Set `HF_TOKEN`
for authenticated downloads. Pyannote may additionally require accepting its
model terms on Hugging Face.

### First realtime window causes queue drops

SpeechBrain and ASR model initialization can make the first window much slower
than later windows. Increase `--max-queue`, pre-download assets, or compare
drop policies through the component sweep.

## Development

Install development dependencies:

```powershell
./install.ps1 -Profile dev
```

Run inference-pipeline tests from the Evaluation Tool directory:

```powershell
../../.venv/Scripts/python.exe -m pytest tests/inference_pipeline -q
```

The detailed dataset-evaluation documentation remains in
`Software Validation from Datasets/Evaluation Tool/README.md`, and inference
component notes are in `README_inference_pipeline.md` in the same directory.

The VAD, speaker-embedding, and diarization component choices and readiness
notes are documented in `docs/SWAPPABLE_SPEECH_COMPONENTS.md`.
