# Stage 8 Environment Profiles

## Contract

`configs/automated_evaluation/environment_profiles.stage8.v1.yaml` is the machine-readable profile contract. Direct dependencies are pinned in `requirements/stage8/`; installed transitive versions are frozen per machine in `.stage8-envs/<profile>/environment.freeze.txt`. Each optional stack is isolated from the Stage 0–7 `.venv`.

| Profile | Platform/device | Purpose | Current machine result |
|---|---|---|---|
| `core-cpu` | Windows/Linux/macOS CPU | Preserve the qualified Stage 0–7 reference | Passed; unchanged |
| `core-cuda` | Windows/Linux NVIDIA CUDA | Single-job Tiny/Base/Small and ECAPA CUDA gate | 4/4 real qualified on RTX 3080 |
| `extended-local` | Cross-platform CPU | Faster-Whisper, Vosk, WebRTC VAD, Resemblyzer | 4/4 real qualified; WebRTC has one warning |
| `onnx` | Cross-platform CPU | Sherpa ASR, VAD, embedding, diarization | 4/4 real qualified |
| `wenet` | Windows/Linux CPU candidate | WeNet v3.1 adapter/runtime | Package installed; required `final.zip` absent |
| `wespeaker` | Cross-platform CPU | WeSpeaker embedding | Real qualified with isolated dependency warnings |
| `credential-diarization` | Cross-platform CPU/GPU | pyannote Community-1 and Falcon | Licence action required for both |
| `nemo-linux-cuda` | Linux NVIDIA CUDA | Composite NeMo diarization | Linux platform and active checkpoints required |

## Reproducible installation

From Anaconda Prompt, Command Prompt, or PowerShell at the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile core-cuda
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile extended-local -DownloadModels
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile onnx -DownloadModels
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile wenet -DownloadModels
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile wespeaker -DownloadModels
```

Use `-Recreate` only to replace the selected `.stage8-envs/<profile>` directory. The script validates that deletion remains under `.stage8-envs`, runs `pip check`, downloads only explicitly selected registered assets, and writes the exact freeze. Model downloads never happen in scenario execution.

On a dedicated Linux/CUDA host:

```bash
cd /path/to/just-peachy
bash scripts/install_stage8_nemo_linux.sh
.stage8-envs/nemo-linux-cuda/bin/python \
  "Software Validation from Datasets/Evaluation Tool/scripts/qualify_extended_backends.py" \
  --profile nemo-linux-cuda --device cuda
```

The Linux script prepares a candidate environment; it does not make NeMo qualified. The active local checkpoints must first be chosen, licensed, downloaded, registered, and hashed, and the real adapter must emit valid repeated turns.

## Compatibility decisions

- `core-cuda` uses pinned Torch/Torchaudio 2.11.0 CUDA 12.8 wheels in its own environment. The ordinary `.venv` remains CPU-only.
- `extended-local` and `onnx` coexist internally but remain separate to reduce native-runtime conflicts and make failures attributable.
- WeNet uses immutable upstream commit `2d8bb9780f5b23da65abee37fd612a1fa2f2f4e8`. Its source archive avoids recursive checkout of unrelated submodules.
- WeSpeaker uses immutable commit `1d4164bdb1dcfee4624093190fd5ecbb19447686`. Its metadata requests `hdbscan==0.8.37`, for which the current Python 3.12 Windows environment has no usable release; this isolated profile deliberately uses `0.8.44` and records that mismatch.
- Credential diarizers stay in a separate profile. Credential values must never enter requirements, YAML, command arguments, logs, test fixtures, manifests, or reports.
- NeMo is not forced into the Windows profiles and is not treated as a simple interchangeable model slot.

The source contract records expected verifier behavior, supported components, incompatible components, assets, credential requirements, and CPU/GPU/CUDA requirements for every profile.
