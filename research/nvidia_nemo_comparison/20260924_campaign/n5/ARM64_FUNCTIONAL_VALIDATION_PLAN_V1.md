# ARM64 functional validation: next executable scope

Status at 2026-09-27 14:23 UTC: preparation only. The existing ARM64 package
passed build/static/loader checks. It has not run a model or saved WAV, and no
CM5 hardware is connected. This document does not promote it to a release.

## Reuse the pinned interfaces

The existing native runtime is revision
97a15afa5caa9bce5baaa86c1184103877af4101. Its installed
include/nemo_speech/asr.h exposes create, streaming_recognize, push_f32,
stream_next, force_endpoint, stream_finish, stream_close and destroy. The
accepted N3 adapter is preserved in the N4 complete-journal prototype; its
n3_asr_native.py is the reference for configuration and event interpretation.

Preserve all of these values when constructing the ARM64 smoke:

- CPU gpu=-1; greedy decoder; explicit A2 or A3 model and its accepted hash.
- Streaming chunk_size=0.16, ctc_left_padding=1.92,
  ctc_right_padding=1.92 and rnnt_right_context=1. Zeroed streaming geometry
  previously failed validation even for RNNT; do not recreate that defect.
- Endpointing enabled, vad_based=false, stop_history_eou_ms=800.
- Request language en-US, interim results and word offsets enabled, automatic
  punctuation enabled, verbatim transcripts true, max_alternatives=1.
- Saved finite mono 16-kHz float32 samples, delivered in 1,280-sample pushes.
  Drain every result after each push, including multiple finals, until NULL.
  Finish once and drain the tail; preserve native unadjusted offsets and words.
- Close each stream before replaying the same source with a new stream on the
  resident recognizer. Compare final-text hashes and sample accounting. Keep
  empty, short-tail and forced-endpoint conformance distinct from real speech.

Do not substitute the bundled CLI defaults for this test without recording a
changed configuration: transcribe.cpp currently pushes 160 ms (2,560 samples
at 16 kHz), whereas the accepted adapter/test pushes 1,280. CLI help/version or
an unconfigured offline transcription cannot establish the required state/flush
parity. A small C-ABI executable can avoid requiring an emulated Python stack;
the shared Python frontend still needs its own ARM64 validation separately.

## Existing assets and execution order

Use the already unpacked QEMU at
/home/amiri/jp-n5-loader-v2/qemu/usr/bin/qemu-aarch64, the existing Arm GNU
12.3.rel1 compiler/sysroot under /home/amiri/jp-n5-native-v1/tools, and the
packaged runtime at /home/amiri/jp-n5-runtime-v1. Verify their recorded hashes
and ELF identity again when admitting execution. No new downloads are required
for that native engineering route. Build files and logs go into a fresh private
local/n5 directory; never overwrite the earlier failed loader or passing v2 run.

Use an exact small saved input already bound by N3 conformance or the accepted
scene manifest, including its original gain and hash. A2's Q8_0 model hash is
d9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d.
A3's is 3fc991d3badad7277c11030a7519832cddaf2057aafed6d4b25147e953a070b1.
Models, audio, event text and reference evidence stay outside Git.

Wait for the active N4 allocation to close; inspect exact owners and obtain a
fresh resource admission before compiling or invoking WSL/QEMU. Record a bounded
wall timeout, one worker/thread, source/tool/runtime/model/input hashes, exact
argv, exit status and output hashes. Keep all failed attempts. The existing
README_ARM64.md contains PowerShell and CMD/Anaconda commands for the build and
loader stages; those commands do not run this still-unimplemented functional test.

A successful model/WAV/state test may be labelled ARM64_FUNCTIONAL_SMOKE with
EMULATED execution explicitly stated. QEMU timings cannot establish CM5 latency,
2-GB memory fit, power or thermals. A native ASR smoke also does not prove the
Python GUI, diarization, embedding, gallery or install/rollback paths. Only
accepted N4 compositions may become N5 release profiles. Live CM5 checks remain
deferred until the user reconnects the device; do not contact it during campaign.