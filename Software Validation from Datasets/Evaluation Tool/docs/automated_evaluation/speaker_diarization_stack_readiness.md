# Speaker Embedding and Diarization Stack Readiness

## Purpose and scientific boundary

This handoff records the bounded software/model preparation for the sixth independent Stage 10 speaker backend, ReDimNet2-B2, and for modular diarization candidates. It documents how to install, qualify, and later run the code. It does not contain a Stage 10 LARGE result or a Stage 11 scientific result.

Speaker recognition and diarization remain separate:

- Stage 10 compares a probe embedding with backend-specific enrollment and calibration. Enrollment vectors and thresholds are never shared across backends.
- Diarization groups local speech windows into anonymous `speaker_XX` clusters. It does not read or assign known-person identities.

The existing ASR path, Stage 4 identities, frozen Stage 10 protocol, existing model preprocessing, and prior result roots are unchanged.

## Inputs and outputs

Inputs are canonical repository audio, the component fragments under `configs/inference/components/`, pinned local model assets under the Git-ignored repository `models/cache/`, and the frozen Stage 10 or Stage 11 manifests when a later scientific run is authorized.

The ReDimNet2 adapter returns one typed 192-dimensional L2-normalized speaker embedding plus runtime/model metadata. The modular diarizer returns anonymous speaker-turn regions containing start time, end time, local label, and segmentation/clustering provenance. Qualification writes secret-free JSON reports; model files, credentials, embeddings, and audio are not committed.

## Six independent speaker models

| Component | Exact learned model | Environment | Framework | Dimension | Input | License status | Bounded qualification | Stage 10 |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `speechbrain_ecapa` | `speechbrain/spkrec-ecapa-voxceleb`, local `embedding_model.ckpt` SHA-256 `0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2` | `.venv` (`core-cpu`) | SpeechBrain/PyTorch | 192 | mono 16 kHz, minimum 0.75 s | source model terms recorded; local cache has no copied license, so redistribution review remains | READY, CPU | eligible |
| `resemblyzer` | Resemblyzer 0.1.4 packaged `pretrained.pt`, SHA-256 `39373b86598fa3da9fcddee6142382efe09777e8d37dc9c0561f41f0070f134e` | `.stage8-envs/extended-local` | Resemblyzer/PyTorch | 256 | mono 16 kHz, minimum 0.75 s | Apache-2.0 repository; packaged-weight provenance remains a redistribution review item | READY | eligible |
| `wespeaker` | VoxCeleb `voxceleb_resnet221_LM`, ResNet221 + TSTP + 80-bin fbank, exact WeSpeaker source commit `1d4164bdb1dcfee4624093190fd5ecbb19447686` | `.stage8-envs/wespeaker` | WeSpeaker/PyTorch | 256 | mono 16 kHz; 25 ms frame, 10 ms shift | code Apache-2.0; official VoxCeleb pretrained weights CC BY 4.0, attribution required | READY_WITH_WARNING | eligible |
| `campplus_speaker_embedding` | `iic/speech_campplus_sv_en_voxceleb_16k` v1.0.2 | `.stage8-envs/onnx` | Sherpa-ONNX/3D-Speaker | 512 | mono 16 kHz, minimum 0.5 s | Apache-2.0 | READY | eligible |
| `eres2net_base_speaker_embedding` | `iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k` v1.0.1 | `.stage8-envs/onnx` | Sherpa-ONNX/3D-Speaker | 512 | mono 16 kHz, minimum 0.5 s | Apache-2.0 | READY | eligible |
| `redimnet2_b2_speaker_embedding` | official PalabraAI ReDimNet2-B2 VoxCeleb2 large-margin `b2-vox2-lm.pt` v1.0.0; source commit `cdc875670034dd7068013ca2ab21ec083a040ff8` | `.stage8-envs/redimnet2` | official native PyTorch | 192 | mono float32 16 kHz, minimum 0.5 s | official repository and distributed weights MIT; commercial-permissive | READY, CPU | eligible |

`sherpa_onnx_speaker_embedding` remains a qualified component ID but resolves to the exact same ERes2Net Base ONNX file and hash as `eres2net_base_speaker_embedding`. It is therefore not a seventh independent learned model.

## ReDimNet2-B2 preprocessing and runtime contract

The adapter passes uncropped, unpadded mono float32 16 kHz waveform to the official model. The model performs waveform mean/standard-deviation normalization, pre-emphasis 0.97, a time-frequency mel frontend with 72 bins, 512-sample FFT, 400-sample Hamming window, 160-sample hop, 20–7600 Hz range, log features, and feature mean normalization. The shared repository speaker contract then L2-normalizes the 192-dimensional output. The qualified CPU path uses float32, evaluation mode, `torch.inference_mode()`, disabled parameter gradients, one Torch thread, local-only assets, and no inference-time download.

The official release reports approximately 3.6 million parameters and 0.95 GMAC for B2. The loaded v1.0.0 checkpoint contains 3,918,862 parameter tensor elements; this observed count is recorded separately from the upstream rounded figure.

## Diarization readiness matrix

| Configuration | Environment | Composition and exact assets | Credential | Load/smoke | Scientific readiness / remaining work |
| --- | --- | --- | --- | --- | --- |
| Existing `sherpa_onnx_diarization` | `.stage8-envs/onnx` | Sherpa pyannote segmentation-3.0 `model.onnx` + the same ERes2Net Base ONNX + Sherpa `FastClusteringConfig` threshold 0.5, CPU float32 | none | READY | authorized Stage 11 backend; existing bounded smoke passed |
| `modular_energy_campplus` | `.stage8-envs/onnx` | energy speech regions -> existing CAM++ v1.0.2 -> deterministic average-link cosine clustering | none | READY | software-ready; clustering threshold is an untuned engineering default; not yet frozen/authorized for Stage 11 |
| `modular_pyannote_campplus` | `.stage8-envs/credential-diarization` | official pyannote segmentation-3.0 revision `e66f3d3b9eb0873085418a7b813d3b369bf160bb` -> existing CAM++ -> clustering | stored HF login needed for acquisition only | READY | software-ready; later Stage 11 authorization and calibration required |
| `modular_pyannote_eres2net` | `.stage8-envs/credential-diarization` | same official segmentation snapshot -> existing ERes2Net Base v1.0.1 -> clustering | stored HF login needed for acquisition only | READY | software-ready; later Stage 11 authorization and calibration required |
| `modular_energy_wespeaker` | `.stage8-envs/wespeaker` | energy speech regions -> exact Stage 10 WeSpeaker ResNet221-LM -> clustering | none | READY | software-ready; upstream WeSpeaker diarization recipes often use a different ResNet34 encoder, which was deliberately not substituted |
| `pyannote_community` | `.stage8-envs/credential-diarization` | complete official Community-1 revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`; its own PyanNet segmentation, WeSpeaker ResNet34-LM embedding, PLDA, and VBx clustering (`threshold=0.6`, `Fa=0.07`, `Fb=0.8`) | stored HF login needed for acquisition only | READY | opaque reference pipeline is bounded-qualified; frozen Stage 11 registry still needs a separate additive authorization update |

The modular implementation accepts any existing speaker-embedding component fragment. A later `pyannote segmentation-3.0 -> ReDimNet2-B2 -> clustering` candidate therefore requires configuration, independent clustering calibration, and qualification rather than a new diarization implementation.

## Clustering contract

`app/inference_pipeline/diarization/clustering.py` implements deterministic average-link agglomerative clustering over cosine similarity using NumPy. Exact ties resolve by earliest original window indices, cluster numbering is stable, non-finite/zero embeddings are rejected, and optional min/max speaker constraints are validated. Each component YAML owns its own `clustering_policy_id` and threshold. The current 0.5 values are engineering smoke defaults only; they are not tuned, pooled, or borrowed from named-speaker recognition.

Overlapping embedding windows are assigned to non-overlapping midpoint intervals, adjacent equal local labels are merged, and output labels are local anonymous `speaker_00`, `speaker_01`, and so on.

## Model assets and licenses

All paths below are repository-relative logical paths resolved through the portable model-path resolver. The files are ignored by Git.

| Asset | Official source / revision | Local path | Observed size | SHA-256 | Framework / license |
| --- | --- | --- | ---: | --- | --- |
| ReDimNet2 B2 weights | PalabraAI release v1.0.0, `b2-vox2-lm.pt` | `models/cache/redimnet2/b2-vox2-lm.pt` | 15,897,450 | `0545a29679a87fe1c662d2bbd05e3b3fe0d1b392832729abaa135e4079a2f77a` | native PyTorch; MIT |
| ReDimNet2 source tree | official commit `cdc875670034dd7068013ca2ab21ec083a040ff8` | `models/cache/redimnet2/source-cdc875670034dd7068013ca2ab21ec083a040ff8` | 2,036,261 | tree `9ad9348bcb79c38e17e63ecd904bf79fac6dde05a3bf55afef9bad53a5ab3210` | Python/PyTorch; MIT |
| ReDimNet2 source archive | same commit | `models/cache/downloads/redimnet2-cdc875670034dd7068013ca2ab21ec083a040ff8.tar.gz` | 1,118,945 | `48ccf0de4d9a7a2f5c0aeccab7d286d1120ee2564074c7c2f7f38311ac8ff028` | acquisition evidence; MIT |
| pyannote segmentation-3.0 | HF revision `e66f3d3b9eb0873085418a7b813d3b369bf160bb` | `models/cache/pyannote/segmentation-3.0` | 5,982,542 | tree `0bd17acc0afbd3ae9b78f0ac2912d660297d59d9c107cf75bb75b39dcb8c7e14` | pyannote.audio; MIT, gated acquisition |
| pyannote Community-1 | HF revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` | `models/cache/pyannote/speaker-diarization-community-1` | 33,695,785 | tree `dc71e4bd2f63c0c2700d1cabac7833c80e1162e44ebc2097aeb91af240be636f` | pyannote.audio; CC BY 4.0, attribution, gated acquisition |
| CAM++ | ModelScope `iic/speech_campplus_sv_en_voxceleb_16k` v1.0.2 | `models/cache/sherpa_onnx/speaker_embedding/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx` | 29,596,978 | `357a834f702b80161e5b981182c038e18553c1f2ca752ed6cec2052365d4129b` | ONNX; Apache-2.0 |
| ERes2Net Base | ModelScope `iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k` v1.0.1 | `models/cache/sherpa_onnx/speaker_embedding/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx` | 39,593,761 | `1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b` | ONNX; Apache-2.0 |
| WeSpeaker tree | official `voxceleb_resnet221_LM`, source commit `1d4164bdb1dcfee4624093190fd5ecbb19447686` | `models/cache/wespeaker/english` | 114,411,934 | tree `bd70550dbfcdaecf387cefcc34d57d1b815fbdd6ee2d62477dd0e1eb176ff962` | PyTorch; code Apache-2.0, weights CC BY 4.0 |
| WeSpeaker weights | same | `models/cache/wespeaker/english/avg_model.pt` | 114,410,390 | `47d76239f1e865b273e31e30f691959061ff6565ed6c4e7be9639a65d9662eb5` | PyTorch; CC BY 4.0 |
| Sherpa segmentation | Sherpa speaker-segmentation release, pyannote segmentation-3.0 conversion | `models/cache/sherpa_onnx/diarization/sherpa-onnx-pyannote-segmentation-3-0/model.onnx` | 5,992,913 | `220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079` | ONNX; bundled model package MIT, Sherpa-ONNX code Apache-2.0 |

Community-1 key internal files are `segmentation/pytorch_model.bin` (5,906,507 bytes, SHA-256 `7ad24338d844fb95985486eb1a464e32d229f6d7a03c9abe60f978bacf3f816e`), `embedding/pytorch_model.bin` (26,646,242 bytes, SHA-256 `6f10ff60898a1d185fa22e1d11e0bfa8a92efec811f11bca48cb8cafebefd929`), `plda/plda.npz`, and `plda/xvec_transform.npz`.

Access terms and a shared physical model folder do not grant redistribution rights. Reproducibility should preserve the authenticated acquisition route and pinned hashes; raw/model binaries must not be added to Git.

## Authentication result

The supported official CLI was `.stage8-envs/credential-diarization/Scripts/hf.exe auth login`. Authentication succeeded for user `amirlaghai` through the interactive prompt; no token value was read from the clipboard, placed in an argument, printed, serialized, or committed. Access and exact-revision resolution succeeded for both gated repositories. Stored authentication is required only to reacquire the snapshots; qualified inference loads local paths with downloads disabled.

## Environment provenance

No validated existing environment was upgraded to support ReDimNet2. The new `.stage8-envs/redimnet2` contains Python 3.12.7, pip 24.2, `torch==2.11.0+cpu`, `torchaudio==2.11.0+cpu`, `numpy==2.2.6`, `scipy==1.15.3`, `scikit-learn==1.7.2`, and `soundfile==0.13.1`.

The isolated `.stage8-envs/credential-diarization` contains Python 3.12.7, pip 24.2, `pyannote-audio==4.0.7`, `huggingface_hub==1.28.0`, `torch==2.11.0`, `torchaudio==2.11.0`, `torchcodec==0.16.0`, `numpy==2.2.6`, `scipy==1.15.3`, `scikit-learn==1.7.2`, `sherpa_onnx==1.13.4`, and `soundfile==0.13.1`.

Existing regression environments remain mapped as before: CAM++ and ERes2Net to `onnx` (`sherpa_onnx==1.13.4`), WeSpeaker to `wespeaker` (exact source commit above), Resemblyzer to `extended-local`, and SpeechBrain ECAPA to `.venv`.

## Install and bounded qualification

From Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"

rem Isolated ReDimNet2 environment and exact official assets
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile redimnet2
".stage8-envs\redimnet2\Scripts\python.exe" "Software Validation from Datasets\Evaluation Tool\scripts\bootstrap_models.py" --redimnet2-b2

rem Credential-gated diarization environment and interactive acquisition
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile credential-diarization
".stage8-envs\credential-diarization\Scripts\hf.exe" auth login
".stage8-envs\credential-diarization\Scripts\python.exe" "Software Validation from Datasets\Evaluation Tool\scripts\bootstrap_models.py" --pyannote

cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest tests\inference_pipeline\test_modular_diarization.py -q
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py speaker-protocol validate --manifest-root benchmarks\stage10\large
```

Qualification inputs are one small existing real-audio fixture plus a too-short fixture; outputs are secret-free backend status, asset identity, dimensions/norms/repeat drift, runtime, and diarization-turn diagnostics. These commands do not run LARGE.

## Bounded evidence

- `redimnet2_bounded.json`: ReDimNet2 loaded the exact official source/checkpoint, returned two finite normalized 192-dimensional outputs, classified the minimum-duration fixture as `too_short`, and had repeat L2 drift 0.0.
- `onnx_bounded.json`: existing Sherpa diarization, CAM++, ERes2Net, and energy->CAM++ all qualified; CAM++ and ERes2Net retained 512-dimensional outputs.
- `wespeaker_bounded.json`: the exact 256-dimensional ResNet221-LM embedder and energy->WeSpeaker modular path ran. WeSpeaker is `READY_WITH_WARNING` because of the pinned-versus-Python-3.12 `hdbscan` metadata override, deprecated `pkg_resources` import from `kaldiio`, and an unused projection tensor during weight load; output validity and repeatability passed.
- `credential_diarization_bounded.json`: Community-1, segmentation->CAM++, and segmentation->ERes2Net all qualified. The adapter supplies decoded in-memory waveform to pyannote, avoiding a Windows external-FFmpeg/TorchCodec path-decoding dependency.
- Deterministic clustering/configuration tests passed, including the configuration-only future pyannote->ReDimNet2 composition.
- The unchanged Stage 10 LARGE manifest validated 960 rows: 450 clean probes, 450 degraded probes, disjoint enrollment/probe and calibration/evaluation sources, disjoint unknown speakers, and no private identity mapping.

## Known limits and next authorization steps

- No Stage 10 LARGE extraction/evaluation and no Stage 11 campaign was started.
- ReDimNet2 CUDA, ONNX export, and deployment performance remain unqualified. The official native CPU path is the scientific comparison target.
- Direct `speaker-protocol extract` covers clean protocol rows. A complete scientific LARGE bundle still requires the existing campaign path to materialize degraded probes with unchanged global item IDs before evaluation.
- Pyannote Community-1 and the modular paths are software-qualified but not yet authorized in the frozen Stage 11 registry. A later task must add scientific authorization, independent clustering calibration, and new immutable result roots.
- Community-1 remains an opaque reference: its internal ResNet34-LM must not be confused with or substituted for the repository's Stage 10 WeSpeaker ResNet221-LM.
- The very short credential-profile smoke emits pyannote/PyTorch's upstream `std()` degrees-of-freedom warning for a one-frame pooling edge case; all three credential-profile paths still returned valid repeatable turns and qualified. This is a smoke-fixture warning, not a suppressed inference failure.
- The current modular pyannote stage collapses local segmentation speaker channels to speech activity before embedding-window clustering. It does not claim that segmentation alone provides persistent speaker identities or overlap-aware cross-window identity.
- Existing redistribution caveats for SpeechBrain cache and Resemblyzer packaged weights remain; no binary is newly redistributed by this work.
