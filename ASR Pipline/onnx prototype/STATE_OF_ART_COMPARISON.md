# STATE OF THE ART COMPARISON

This document is intentionally blunt.

## 1. Core truth

**ONNX is not the state of the art.**
It is a **deployment/runtime standard**.

State-of-the-art quality comes from the underlying model family, not from the file format.

So the correct comparison is:

- **best models that can realistically be deployed through ONNX**
versus
- **absolute frontier models regardless of deployment pain**

Those are not the same thing.

---

## 2. ASR comparison

## Absolute frontier
NVIDIA NeMo states that **Canary-Qwen-2.5B** reached **5.63% WER** on the English Open ASR Leaderboard. That is the kind of result you should treat as frontier-scale ASR, not as a Raspberry Pi product default. See `REFERENCES.md` entries 35 and the report source note.

## Strong ONNX-friendly options
Within the ONNX-friendly, local-deployable world, the practical model families in this project are:

### A. Whisper exported to ONNX
**Strengths**
- proven
- strong general ASR quality
- large model ecosystem
- sherpa-onnx already supports Whisper ONNX usage and export flow

**Weaknesses**
- large models are heavy for Pi / edge
- non-streaming use is the natural starting point
- tokenization / decode wiring is more annoying without a wrapper, which is why sherpa-onnx matters

### B. NeMo Parakeet ONNX via sherpa-onnx
**Strengths**
- modern speech family
- supported in sherpa-onnx docs
- int8 variants exist in the sherpa-onnx ecosystem
- potentially better Pareto point than Whisper in some deployment cases

**Weaknesses**
- fewer battle-tested community deployment examples than Whisper
- you still need real benchmarks on your datasets

### C. Moonshine ONNX via sherpa-onnx
**Strengths**
- very deployment-oriented
- quantized variants highlighted in sherpa-onnx docs
- strong candidate for Pi / edge fallback

**Weaknesses**
- likely not your highest-accuracy desktop choice
- should be treated as edge fallback, not assumed winner

## Recommendation
### For desktop evaluation-first
Use **Whisper large-v3 or turbo** first.

### For Pi / edge
Benchmark **Moonshine** and **Parakeet int8**.

---

## 3. VAD comparison

For this project there is little value in overcomplicating VAD.

### Silero VAD
This is the obvious v1 choice because it is:
- fast
- lightweight
- ONNX-friendly
- permissively licensed
- widely used in real systems

Could there be another model that beats it in some benchmark?
Yes.

Does that justify extra engineering now?
No.

### Recommendation
Use **Silero VAD** first and move on.

---

## 4. Speaker embedding comparison

This is where you need to distinguish between:

- **research-best speaker verification systems**
- **deployable ONNX speaker embedding systems**
- **your actual enrollment problem**

## Practical ONNX-first candidates

### A. WeSpeaker CAM++
**Why it is attractive**
- direct ONNX artifact exists
- toolkit is production-oriented
- code is Apache-2.0
- ONNX deployment is part of the toolkit story

**Why it is a strong v1**
You can start matching enrolled speakers without inventing your own export path first.

### B. SpeechBrain ECAPA exported to ONNX
**Why it matters**
- SpeechBrain ECAPA is a very strong baseline and its VoxCeleb cleaned test EER is reported as **0.80%** in the official model card
- code and model are Apache-2.0

**Why it is not the first implementation choice**
- it is not already packaged as your cleanest ONNX production path
- you would own the export and validation steps
- that is a better benchmarking branch than a first milestone

## Recommendation
- implement **WeSpeaker CAM++ ONNX** first
- benchmark later against an exported **ECAPA** path

---

## 5. Diarization comparison

This is the most important honesty section.

## Strong public baseline
pyannote explicitly positions its open and premium diarization models as state of the art and publishes benchmark comparisons across AMI, DIHARD, VoxConverse, and other datasets.

## ONNX-native option
sherpa-onnx supports speaker diarization.

## Real conclusion
For generic diarization quality, the ONNX path is **not the obvious state-of-the-art leader**.

That does **not** mean the ONNX path is wrong for your product.

It means:
- do not anchor version 1 on open-world diarization,
- build enrolled-speaker matching first,
- and treat pyannote as a gap-analysis benchmark later.

---

## 6. Punctuation comparison

This is not where you should spend strategic energy.

Use sherpa-onnx punctuation once the core path works.

---

## 7. Where ONNX is genuinely strong

ONNX is strong for:
- cross-platform runtime consistency
- local inference
- Windows/macOS/Linux portability
- CPU-first deployments
- model packaging
- post-training optimization
- embedded and edge packaging
- using one runtime layer across many model families

For your project, that is a real advantage.

---

## 8. Where ONNX is genuinely weak

ONNX is weaker for:
- being the first place frontier research models appear
- fully packaged best-in-class diarization
- training-time convenience
- avoiding all glue code

---

## 9. What “validated against state of the art” should mean here

It should **not** mean:
- “use the most powerful research model regardless of deployment cost.”

It **should** mean:
- compare your ONNX stack against the strongest realistic baselines,
- understand where it is likely behind,
- and pick the right compromise for the product.

### Correct statement for this project
The proposed ONNX-first stack is **near state-of-practice for deployable local speech systems**, especially for:
- local ASR,
- VAD,
- speaker enrollment / matching,
- edge deployment.

It is **not** the obvious state-of-the-art path for generic diarization.

That is the correct engineering conclusion.

---

## 10. Final recommendation

### Use this as the primary stack
- Silero VAD
- sherpa-onnx Whisper backend
- WeSpeaker CAM++ ONNX
- sherpa-onnx punctuation
- ONNX Runtime
- Olive later

### Benchmark against these later
- Moonshine backend
- Parakeet backend
- SpeechBrain ECAPA exported ONNX speaker model
- pyannote diarization baseline

That gives you a serious ONNX-first system without pretending ONNX wins every category.
