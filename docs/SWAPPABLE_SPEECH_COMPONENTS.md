# Swappable VAD, Speaker Embedding, and Diarization Components

> **Historical design document.** Current component status, environment boundaries,
> commands, and limitations are documented under
> `Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/`.
> Use `final_acceptance_audit.md` as the source of truth.

The Evaluation Tool now exposes each requested backend through the existing
component registry and `PipelineConfig` component slots. Model objects are
still loaded lazily: resolving a configuration does not load weights, contact a
model hub, or require a credential.

This setup deliberately does **not** implement the combinational evaluation
framework described in `message(1).txt`. That document was used only to keep
component names, availability failures, and local model paths suitable for a
future qualification layer.

## VAD slot

| Component name | Config fragment | Runtime/model | Local status |
|---|---|---|---|
| `silero_vad` | `components/vad/silero.yaml` | `silero-vad` packaged model | Real inference smoke-tested |
| `webrtc_vad` | `components/vad/webrtc.yaml` | `webrtcvad-wheels`; no separate weights | Real inference smoke-tested |
| `sherpa_onnx_vad` | `components/vad/sherpa_onnx.yaml` | `sherpa-onnx` + local `silero_vad.onnx` | Real inference smoke-tested |

The pre-existing `energy_vad` and disabled `no_op_vad` choices remain
available.

## Speaker-embedding slot

| Component name | Config fragment | Runtime/model | Local status |
|---|---|---|---|
| `speechbrain_ecapa` | `components/speaker_embedding/speechbrain_ecapa.yaml` | SpeechBrain ECAPA VoxCeleb cache | Real inference: 192 dimensions |
| `wespeaker` | `components/speaker_embedding/wespeaker.yaml` | Pinned WeSpeaker runtime + local English ResNet221-LM | Real inference: 256 dimensions |
| `sherpa_onnx_speaker_embedding` | `components/speaker_embedding/sherpa_onnx.yaml` | Sherpa-ONNX + local 3D-Speaker ERes2Net model | Real inference: 512 dimensions |
| `resemblyzer` | `components/speaker_embedding/resemblyzer.yaml` | Resemblyzer packaged `pretrained.pt` | Real inference: 256 dimensions |

Every adapter produces the same normalized `SpeakerEmbedding` contract, so it
can feed the existing cosine enrollment matcher. Enrollment databases are
model-specific: changing embedding backend requires rebuilding enrollment
embeddings and changing `runtime_model_id`; vectors from different backends or
dimensions must not be compared.

## Diarization slot

| Component name/approach | Config | Runtime/model | Local status |
|---|---|---|---|
| Simple VAD + speaker-change evidence + enrollment matching | `simple_vad_speaker_change_enrollment.yaml` | Existing `SpeakerEvidenceAccumulator`, SpeechBrain ECAPA, cosine matcher | Offline VAD chunks use 2-of-3 confirmation; realtime uses the same state model |
| `pyannote_community` | `components/diarization/pyannote_community.yaml` | `pyannote.audio` Community-1 | Adapter wired; gated model and complete pyannote environment still required |
| `sherpa_onnx_diarization` | `components/diarization/sherpa_onnx.yaml` | Local pyannote segmentation ONNX + 3D-Speaker model + clustering | Real inference smoke-tested |
| `picovoice_falcon` | `components/diarization/picovoice_falcon.yaml` | `pvfalcon` wheel (includes native model/runtime) | Runtime installed; `PICOVOICE_ACCESS_KEY` required to run |
| `nemo_diarization` | `components/diarization/nemo_diarization.yaml` | Current YAML selects NeMo `ClusteringDiarizer` | Linux-only adapter path is wired but local NeMo models/runtime are not qualified; valid MSDD configs can dispatch `NeuralDiarizer`, but no MSDD config or assets are shipped |

The simple approach is intentionally a composition of existing VAD,
segmentation, speaker-embedding, and speaker-matching blocks rather than a
fake standalone diarizer. The offline profile and realtime runner apply the
existing 2-of-3 evidence confirmation behavior. Tentative evidence remains
`Unknown` in final transcript labels until it is confirmed.

## Selecting a component

A full inference config can swap a slot by changing only its component
reference, for example:

```yaml
components:
  vad: components/vad/sherpa_onnx.yaml
  segmentation: components/segmentation/vad_chunks.yaml
  diarization: components/diarization/sherpa_onnx.yaml
  asr: components/asr/whisper_base.yaml
  speaker_embedding: components/speaker_embedding/resemblyzer.yaml
  speaker_matching: components/speaker_matching/cosine_threshold.yaml
```

These selections are independent at configuration time. Runtime qualification
must still reject combinations with missing credentials/assets and must rebuild
enrollment data when the embedding model changes. Those future combination and
qualification rules belong in the evaluation framework requested for the next
phase.

## Installation and assets

Use the full profile for all cross-platform optional runtimes:

```powershell
.\install.ps1 -Profile full -DownloadModels
```

The reproducible model bootstrap flags are:

```powershell
python scripts/bootstrap_models.py `
  --speechbrain-ecapa --silero --wespeaker `
  --sherpa-vad --sherpa-speaker-embedding --sherpa-diarization `
  --nemo-config
```

Pyannote model access cannot be automated without accepting its Hugging Face
terms and providing `PYANNOTE_AUTH_TOKEN`. Falcon cannot initialize without a
Picovoice AccessKey in `PICOVOICE_ACCESS_KEY`. NeMo is isolated in
`requirements/nemo.txt` because its supported platform/CUDA stack should not be
forced into the normal Windows installation.

Public implementation references:

- Sherpa-ONNX VAD and speaker diarization: <https://k2-fsa.github.io/sherpa/onnx/>
- WeSpeaker Python API and pretrained models: <https://github.com/wenet-e2e/wespeaker>
- Resemblyzer: <https://github.com/resemble-ai/Resemblyzer>
- Picovoice Falcon: <https://picovoice.ai/docs/quick-start/falcon-python/>
- NeMo diarization: <https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/speaker_diarization/intro.html>
