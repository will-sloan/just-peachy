# Credential, licence, and model-asset setup

The CPU and CUDA Whisper Base campaigns require **no API key**. Pyannote,
Falcon, NeMo, and WeNet are excluded from its runnable work. The steps below are
for future component qualification and must be performed only by the owner of
the relevant account/licence.

## Production CPU/CUDA asset setup

Both modes require the same local asset and prohibit inference-time downloads:

- path: `models/cache/whisper/base.pt`;
- bytes: 145,262,807;
- SHA-256: `ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E`.

Use the supported setup front door from the repository root:

```powershell
# CPU environment and model
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cpu -InstallFFmpeg -DownloadModels

# CUDA environment and the same model (run instead for CUDA)
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cuda -InstallFFmpeg -DownloadModels
```

The CPU environment is `.venv` with CPU PyTorch. CUDA is isolated in
`.stage8-envs/core-cuda` with PyTorch 2.11.0+cu128. Neither command changes raw
datasets. Licensed datasets and the exact Dining Room and Restaurant RIRs must
be linked locally by the operator. Bedroom remains unresolved and must not be
substituted.

Check presence without revealing values:

```powershell
python scripts/launch_readiness_probe.py credentials
```

The command prints only `pyannote: READY/MISSING` and `falcon: READY/MISSING`.
It returns 0 only when both are ready and 2 when either is missing.

## Pyannote Community-1

- Expected model: `pyannote/speaker-diarization-community-1` (gated snapshot).
- Provider and terms: [official Community-1 model page](https://huggingface.co/pyannote/speaker-diarization-community-1). Sign in to a Hugging Face account, accept the model's access conditions, and share the required contact information on that page.
- Token: create a read or fine-grained read token following the [Hugging Face token guidance](https://huggingface.co/docs/hub/security-tokens); scope it only as broadly as needed to read the model.
- Project variables: `PYANNOTE_LICENSE_ACCEPTED=1` and
  `PYANNOTE_AUTH_TOKEN=<secret>`.
- Cache: `models/cache/pyannote`.

In a private PowerShell process, enter the token without printing it:

```powershell
$env:PYANNOTE_LICENSE_ACCEPTED = '1'
$pyannoteSecureToken = Read-Host -AsSecureString 'Hugging Face token'
$pyannoteTokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pyannoteSecureToken)
try {
  $env:PYANNOTE_AUTH_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pyannoteTokenPointer)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pyannoteTokenPointer)
}

Set-Location <just-peachy-repository>
powershell -ExecutionPolicy Bypass -File scripts/install_stage8_profile.ps1 `
  -Profile credential-diarization -DownloadModels
Set-Location 'Software Validation from Datasets/Evaluation Tool'
python scripts/launch_readiness_probe.py credentials
..\..\.stage8-envs\credential-diarization\Scripts\python.exe `
  scripts/qualify_extended_backends.py `
  --profile credential-diarization `
  --backend pyannote_community
```

Success requires two real, contract-valid diarization outputs and retained
qualification evidence; token presence alone is not qualification. A 401/403,
missing snapshot, unaccepted terms, or `licence_action_required` remains a
blocker. Clear the process variables when finished.

## Picovoice Falcon

- Provider: [Picovoice Falcon Python quick start](https://picovoice.ai/docs/quick-start/falcon-python/) and [Falcon Python API](https://picovoice.ai/docs/api/falcon-python/).
- Owner action: create/sign in to a Picovoice account, review and accept the
  applicable terms, and generate an AccessKey in the Picovoice Console.
- Project variables: `PICOVOICE_LICENSE_ACCEPTED=1` and
  `PICOVOICE_ACCESS_KEY=<secret>`.
- Package/profile: `pvfalcon` in `credential-diarization`; there is no shared
  model file in the project asset registry.

```powershell
$env:PICOVOICE_LICENSE_ACCEPTED = '1'
$falconSecureKey = Read-Host -AsSecureString 'Picovoice AccessKey'
$falconKeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($falconSecureKey)
try {
  $env:PICOVOICE_ACCESS_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($falconKeyPointer)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($falconKeyPointer)
}

Set-Location <just-peachy-repository>
powershell -ExecutionPolicy Bypass -File scripts/install_stage8_profile.ps1 `
  -Profile credential-diarization
Set-Location 'Software Validation from Datasets/Evaluation Tool'
python scripts/launch_readiness_probe.py credentials
..\..\.stage8-envs\credential-diarization\Scripts\python.exe `
  scripts/qualify_extended_backends.py `
  --profile credential-diarization `
  --backend picovoice_falcon
```

Success means real anonymous turns validate twice. Authentication errors,
unsupported-platform errors, or licence status remain explicit blockers.

## NVIDIA NeMo diarization

NeMo has no project API key, but the current profile is Linux-only and requires
an NVIDIA GPU, working CUDA/driver, Python 3.12, pinned packages, a local
`models/cache/nemo/diarization/config.yaml`, and every active local checkpoint
referenced by that config. Windows `core-cpu` is incompatible. Follow the
[official NeMo installation documentation](https://docs.nvidia.com/nemo-framework/user-guide/25.04/installation.html) and [speaker diarization model documentation](https://docs.nvidia.com/nemo-framework/user-guide/26.02/nemotoolkit/asr/speaker_diarization/models.html), then use the repository's pinned script:

```bash
bash scripts/install_stage8_nemo_linux.sh
.stage8-envs/nemo-linux-cuda/bin/python \
  "Software Validation from Datasets/Evaluation Tool/scripts/qualify_extended_backends.py" \
  --profile nemo-linux-cuda --backend nemo_diarization --device cuda
```

The selected checkpoint identities, sources, licences, and hashes must be added
to the asset registry before qualification. The current active checkpoints are
unresolved, so this remains blocked; do not enable downloads in inference.

## WeNet ASR

The configured adapter calls `torch.jit.load(final.zip)`. The repository-
approved archive currently contains `final.pt`, so it is retained only as
provenance and does not satisfy the runtime contract. Renaming it is forbidden.
The expected location is
`models/cache/wenet/asr/librispeech_u2pp_conformer_exp/final.zip`, alongside
`units.txt`. Use only an official, licence-reviewed source such as the
[WeNet project](https://github.com/wenet-e2e/wenet); no compatible download URL
is currently approved in this repository.

After an exact compatible asset is acquired and hashed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_stage8_profile.ps1 -Profile wenet
.stage8-envs\wenet\Scripts\python.exe `
  "Software Validation from Datasets\Evaluation Tool\scripts\qualify_extended_backends.py" `
  --profile wenet --backend wenet
```

Success requires the pinned package and local checkpoint to load and produce a
real transcript twice. Until then, status is unavailable—not merely untested.

## Security rules

Never place tokens/keys in Git, YAML, JSON, reports, screenshots, chat, command
arguments, or transfer packages. Use process-scoped variables or a trusted
secret manager, never print them, and clear them after qualification. Licence
acknowledgement variables must be set only after the owner personally accepts
the upstream terms.
