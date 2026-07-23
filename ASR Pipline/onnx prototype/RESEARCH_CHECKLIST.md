# RESEARCH CHECKLIST

Use this after the first pipeline is running.

## A. ASR model comparison
Benchmark on your existing Evaluation Tool:
- Whisper large-v3 ONNX
- Whisper turbo / distil-large-v3 ONNX
- Moonshine quantized ONNX
- NeMo Parakeet int8 ONNX

Collect:
- WER
- runtime per utterance
- peak memory
- model disk size

## B. Speaker embedding comparison
Benchmark:
- WeSpeaker CAM++ ONNX
- SpeechBrain ECAPA exported to ONNX

Collect:
- known-speaker accuracy
- false known-speaker assignments
- Unknown rate
- sensitivity to prompt mismatch

## C. Enrollment design
Test:
- one fixed sentence
- three fixed sentences
- one paragraph
- same-content enrollment vs different-content evaluation
- average embedding vs exemplar bank

Collect:
- cosine score distributions
- within-speaker variance
- between-speaker margin
- threshold stability

## D. VAD impact
Test:
- no VAD
- trim-only VAD
- segmentation VAD

Collect:
- WER change
- runtime change
- missing-speech failure cases
- false truncation cases

## E. Optimization
After baseline:
- fp32 vs int8
- ONNX vs ORT format
- CPUExecutionProvider vs optional Arm NN EP on Pi

Collect:
- latency
- throughput
- model size
- accuracy drop

## F. Gap to non-ONNX best baseline
For diarization only:
- compare later against pyannote
- use this to measure the cost of staying ONNX-first
- do not block v1 on closing that gap
