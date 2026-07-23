# LICENSE MATRIX

This is a technical product-oriented summary, not legal advice.

## Interpretation rules

### MIT
- generally usable in commercial products
- modified code can be shipped in proprietary products
- preserve copyright and license notices
- permissive, but less explicit about patents than Apache-2.0

### Apache-2.0
- generally usable in commercial products
- modified code can be shipped in proprietary products
- preserve notices and state changes
- includes an explicit patent grant
- not a copyleft license

## Important caveat

For ML systems, always separate:

1. **toolkit code license**
2. **model weights license**
3. **training data / model-card restrictions**
4. **privacy / biometric obligations in your product**

Do not assume code license == model license.

---

| Component | Role in this project | Code license | Commercial product use? | Can modified code be shipped in proprietary product? | Main caveat |
|---|---|---:|---|---|---|
| ONNX | model format, checker, graph utilities | Apache-2.0 | Yes | Yes | preserve notices; Apache obligations |
| ONNX Runtime | core inference engine | MIT | Yes | Yes | preserve MIT notice |
| ONNX Runtime Extensions | custom ops / pre-post graph packaging | MIT | Yes | Yes | useful later, not required first |
| Olive | optimization / quantization / packaging | MIT | Yes | Yes | optimization tool only; model license still matters |
| Hugging Face Optimum | ONNX/ORT export helper | Apache-2.0 | Yes | Yes | exported model weights may have separate terms |
| sherpa-onnx | high-level ONNX speech runtime | Apache-2.0 | Yes | Yes | bundled / downloaded model licenses vary by upstream model |
| Silero VAD | VAD model/tooling | MIT | Yes | Yes | verify exact model artifact provenance you ship |
| OpenAI Whisper code | reference model family / exports | MIT | Yes | Yes | preserve notice |
| OpenAI Whisper weights | ASR model weights | MIT | Yes | Yes | model weights are permissive, but still verify redistribution path |
| WeSpeaker code | speaker verification / embedding toolkit | Apache-2.0 | Yes | Yes | checkpoint licenses may differ from code |
| WeSpeaker CAM++ ONNX model card | speaker embedding model candidate | Apache-2.0 | Generally yes | N/A (model artifact) | verify exact checkpoint / hosting artifact you ship |
| SpeechBrain code | alternative speaker embedding toolkit | Apache-2.0 | Yes | Yes | export path to ONNX is your responsibility |
| SpeechBrain ECAPA model card | alternative speaker embedding baseline | Apache-2.0 | Generally yes | N/A (model artifact) | not ONNX-native by default; export required |
| pyannote.audio code | non-ONNX diarization benchmark | MIT | Yes | Yes | model access / premium services differ from toolkit |
| pyannote Community-1 model | diarization baseline | check model card / access terms | Likely usable under its terms, but verify | N/A | not an ONNX-native production path for this project |

---

## Recommended compliance posture for this project

### Safe core choices
These are the cleanest from a product engineering standpoint:
- ONNX
- ONNX Runtime
- ONNX Runtime Extensions
- Olive
- Optimum
- sherpa-onnx
- Silero VAD
- Whisper
- WeSpeaker CAM++ model **if you keep the exact Apache-2.0 artifact and verify redistribution**

### Things to verify before shipping
- any sherpa-onnx pre-exported model bundle downloaded from Hugging Face
- any non-Whisper ASR model bundle
- any speaker model that is not clearly labeled with a permissive license
- any dataset-derived restriction in model cards

### Product caveat outside OSS licensing
Your product stores speaker embeddings / voiceprints.

That is a **biometric / privacy** issue independent of the OSS license.  
This package does not provide legal advice for that area.

---

## Decision for v1

For the cleanest commercial posture, the simplest v1 stack is:

- ONNX / ONNX Runtime / Olive / Optimum / ORT Extensions
- sherpa-onnx runtime
- Silero VAD
- Whisper ONNX export
- WeSpeaker CAM++ ONNX model only after verifying the exact artifact and keeping the model card with the build records

That is the lowest-friction permissive stack in the ONNX ecosystem for your use case.
