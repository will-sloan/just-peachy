# N3 native streaming ASR

`n3_asr_native.py` binds the reviewed NeMo-Speech.cpp C ABI at commit
97a15afa5caa9bce5baaa86c1184103877af4101. It accepts only the two exact official
N3 A2/A3 Q8 artifacts. The baseline and A1 architecture are separate.

Input: a `just-peachy.n3.native-asr.v1` binding with exact model and runtime
revisions, SHA-256, all colocated runtime dependency hashes, explicit device
(-1 CPU or 0 CUDA), language en-US, right context (0/1/6/13), greedy decoder and
800 ms endpoint history; then finite mono float32 blocks at 16 kHz.
Output: ordered partial/final raw text events, untouched native word offsets,
actual input sample counts and monotonic availability. Native PnC is retained
without another PnC pass. No reference text, speaker boundaries or decoder bias
enters inference. EOU is not interpreted as a speaker change.

The caller owns the recognizer and exactly one stream at a time. `feed` returns
all native results; `finish_events` flushes once and is idempotent. `close`
releases ownership; it does not pretend an unflushed stream completed. Retain all
returned finals even when a single push produces several. No model-name defaults,
VAD model, acoustic masking, ITN, profanity filter, speech contexts or diarization
sidecar are activated. Model offsets are not fitted or clamped to improve scores.
Use a fresh process to switch native CPU/CUDA library directories on Windows.

Nominal configuration: right context 1 (160 ms model context); lower-buffer
contrast 0 (80 ms). These are buffering settings, not measured live latency.
CPU portability does not establish ARM64 operation or a 2-GB system fit.

From the campaign worktree, import-only syntax verification (loads no weights):

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m py_compile prototype/vendor/edge_speech_pipeline/n3_asr_native.py
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m py_compile prototype/vendor/edge_speech_pipeline/n3_asr_native.py
```

Actual saved-audio commands and run receipts are maintained in the campaign N3
README as the evaluation runner is admitted. This module alone is not a completed
backend comparison. Keep weights and private transcripts outside Git.
