# Extended Backend Setup and Operator Actions

## Stage boundary and safety

Stage 8 prepares isolated environments and proves adapter contracts. It does not run benchmark screening, select winners, compute diarization science metrics, or enable parallel GPU work.

No account was created, no licence was accepted for the user, and no credential was generated or saved. Those actions require the user's identity and consent. Tokens and access keys must be supplied only through environment variables and cleared after use; qualification artifacts record only `true`/`false` presence.

## What is already set up

The following are installed in isolated, frozen environments and have real repeated qualification evidence:

- Faster-Whisper 1.2.1, Vosk 0.3.45, WebRTC VAD 2.0.14, and Resemblyzer 0.1.4 in `extended-local`;
- Sherpa-ONNX 1.13.4 ASR, VAD, speaker embedding, and diarization in `onnx`;
- WeSpeaker at immutable commit `1d4164bdb1dcfee4624093190fd5ecbb19447686` in `wespeaker`;
- the core CUDA gate for Whisper Tiny, Base, Small, and SpeechBrain ECAPA in `core-cuda`.

Registered assets were downloaded through `scripts/bootstrap_models.py`, verified against archive hashes where available, unpacked under `models/cache`, and re-inventoried by content. The machine inventory contains per-file SHA-256 values, aggregate tree hashes, sizes, acquisition time, method, storage path, environment, source, and licence notes.

## Actions still required from the user

### 1. WeNet checkpoint

The pinned WeNet v3.1 Python runtime loads a TorchScript runtime package named `final.zip`. The official archive currently registered and downloaded contains a training checkpoint named `final.pt`; renaming it would not convert its format and is prohibited. Obtain an official compatible runtime export containing at least `final.zip` and `units.txt`, verify its model card/licence, record its source and SHA-256, and place it in:

```text
models/cache/wenet/asr/librispeech_u2pp_conformer_exp/
```

Then run:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.stage8-envs\wenet\Scripts\python.exe "Software Validation from Datasets\Evaluation Tool\scripts\inventory_stage8_assets.py"
.stage8-envs\wenet\Scripts\python.exe "Software Validation from Datasets\Evaluation Tool\scripts\qualify_extended_backends.py" --profile wenet
```

Do not mark WeNet qualified until it produces two real contract-valid transcripts offline.

### 2. pyannote Community-1

The user must personally create or use a Hugging Face account, accept the conditions on the registered Community-1 model page, create a least-privilege read-only token, and supply it for the current shell. Do not paste the token into a document or command saved in shell history.

PowerShell variable names:

```powershell
$env:PYANNOTE_LICENSE_ACCEPTED = '1'
$env:PYANNOTE_AUTH_TOKEN = '<supply from an approved secret manager>'
```

Anaconda Prompt/Command Prompt variable names:

```bat
set PYANNOTE_LICENSE_ACCEPTED=1
set PYANNOTE_AUTH_TOKEN=<supply from an approved secret manager>
```

After setting them, prepare and qualify:

```bat
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile credential-diarization -DownloadModels
.stage8-envs\credential-diarization\Scripts\python.exe "Software Validation from Datasets\Evaluation Tool\scripts\qualify_extended_backends.py" --profile credential-diarization --backend pyannote_community
```

Clear the variables after the run (`Remove-Item Env:\PYANNOTE_AUTH_TOKEN` in PowerShell or `set PYANNOTE_AUTH_TOKEN=` in Command Prompt). Inspect the output with a secret scanner before transfer.

### 3. Picovoice Falcon

The user must personally create or use a Picovoice account, accept its terms, generate an approved access key, and supply it only through `PICOVOICE_ACCESS_KEY`. Also set `PICOVOICE_LICENSE_ACCEPTED=1` after personal acceptance. Then install the same `credential-diarization` profile and run the qualifier with `--backend picovoice_falcon`. Clear both variables afterward. Never put the access key in a source file, YAML, manifest, report, issue, chat, or test.

### 4. NeMo Linux/CUDA

Use a dedicated Linux machine, WSL2 installation, or Linux CUDA container with an NVIDIA device and Python 3.12. This Windows machine currently has no qualifying Linux runtime. Run `scripts/install_stage8_nemo_linux.sh`, then select the actual VAD, embedding, clustering/MSDD, and diarization checkpoints referenced by the resolved NeMo configuration. Record each source, licence, filename, size, SHA-256, and local path in the model registry before qualification. NeMo remains `platform_required` until a real Linux/CUDA output passes the Stage 8 contracts.

## Asset inventory and evidence commands

From the Evaluation Tool directory:

```bat
..\..\.stage8-envs\extended-local\Scripts\python.exe scripts\inventory_stage8_assets.py
..\..\.venv\Scripts\python.exe scripts\consolidate_stage8_qualification.py
```

Inputs are the versioned registries and local cache. Outputs are `runs/extended_backend_qualification/model_asset_inventory.json`, each profile JSON, `qualification_summary.json`, and its SHA-256 sidecar. The consolidator validates exact 13-backend coverage and rejects duplicate, missing, or unexpected results.

## No implicit downloads

Qualification forces `allow_model_downloads: false`. A component config that permits implicit download is rejected. Assets may be acquired only in the explicit setup step through the bootstrap script or a documented official source, then hashed. Scenario execution must remain offline-capable and cannot mutate the model cache.
