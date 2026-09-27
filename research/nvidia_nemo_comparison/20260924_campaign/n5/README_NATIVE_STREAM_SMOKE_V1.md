# Saved-audio native streaming harness

Purpose: `native_stream_smoke_v1.cpp` exercises the pinned NeMo C ABI with a
saved WAV in a native or emulated ARM64 process. It creates one CPU recognizer,
then closes six independent streams: empty, one sample, 1,281-sample tail,
complete saved source, repeated source and forced endpoint. It drains every
result after each 1,280-sample push and after finish, records unmodified native
text/word offsets, and compares final text/word signatures across the two full
streams on the resident recognizer. No device, playback or network API is used.

Status: source preparation only; not compiled or executed. A successful binary
exit establishes only these conformance checks. An outer admitted execution must
verify and bind model, WAV, header, runtime dependencies, executable and tools;
the C++ binary explicitly does not verify their hashes itself. Actual GUI,
diarization, embedding, install/rollback and CM5 resource checks remain separate.
QEMU timings and host RAM do not establish CM5 latency or 2-GB suitability.

Inputs: exactly two positional paths, a previously verified A2/A3 Q8_0 model and
an existing saved mono 16-kHz RIFF WAV (PCM16 or IEEE float32). The WAV must have
1,281–960,000 frames, finite samples in [-1,1] and at most 16 MiB. Unsupported
WAV extensible/RF64 formats, rate/channel changes and malformed chunk sizes fail
before loading the model. PCM16 is scaled by 1/32768; float32 is unmodified.
No resampling or gain change is performed. Source, model and events stay private.

Output: UTF-8 JSONL on stdout, bounded to 16 MiB; native diagnostic text can appear
on stderr and must be separately bounded by the outer process. Each result
records its case, push/finish phase, sample count, final flag and native values.
The terminal reports `PASS_NATIVE_STREAM_CONFORMANCE_ONLY` only after six stream
closures, full-source final parity and recognizer destruction. Failures retain
earlier output and return 1. The outer validator must parse every line, require
exactly one final terminal, verify all six case closures and the exact argv,
and preserve stdout/stderr/exit status and process ownership receipts.

## Admission and compilation

Do not invoke WSL, QEMU, compilers or a diagnostic Python while an exclusive N4
application allocation is active. First verify fresh heartbeat/PID creation
identities, all prior owners closed, disk floors C: 50 GiB/G: 75 GiB, the admitted
CPU/download/payload limits, and remaining time before the packaging reserve.
Use one worker and one Linux logical CPU at nice10, with an externally enforced
wall timeout and private output cap. Do not connect to the Pi during this campaign.

Reuse the existing Arm GNU 12.3.rel1 compiler, matching sysroot, generic armv8-a
runtime and pinned header (revision 97a15afa5caa9bce5baaa86c1184103877af4101).
The commands below are templates for the later admitted execution, not an
already-qualified runnable release. Set `OUT` to a fresh private WSL directory;
the output directory must exist only after the outer owner has admitted it.

PowerShell, CMD and Anaconda Prompt all invoke the same WSL command interface:

```text
wsl.exe -d Ubuntu -- bash /path/to/the/admitted-build-and-run.sh
```

The admitted shell script must resolve these existing paths and record its exact
contents and hashes before execution. No new conda environment is needed.

```bash
ARM=/home/amiri/jp-n5-native-v1/tools/arm-gnu-toolchain-12.3.rel1-x86_64-aarch64-none-linux-gnu
SYSROOT="$ARM/aarch64-none-linux-gnu/libc"
RUNTIME=/home/amiri/jp-n5-runtime-v1
SOURCE=/mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/native_stream_smoke_v1.cpp
INCLUDE=/mnt/g/Just_Peachy_N1/20260924_campaign/local/assets/source/NeMo-Speech.cpp-97a15afa5caa9bce5baaa86c1184103877af4101/include
# OUT, MODEL and WAV are absolute private paths from the reviewed admission.
# CPU is one permitted Linux CPU from the fresh affinity census.
taskset -c "$CPU" nice -n 10 "$ARM/bin/aarch64-none-linux-gnu-g++" \
  --sysroot="$SYSROOT" -std=c++17 -O2 -march=armv8-a -Wall -Wextra -Werror \
  -I "$INCLUDE" "$SOURCE" -L "$RUNTIME/lib" \
  -Wl,-rpath-link,"$RUNTIME/lib" -lnemo_speech_asr_c -o "$OUT/native_stream_smoke_v1"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
taskset -c "$CPU" nice -n 10 timeout --signal=TERM --kill-after=10s 1800s \
  /home/amiri/jp-n5-loader-v2/qemu/usr/bin/qemu-aarch64 -L "$SYSROOT" \
  -E LD_LIBRARY_PATH="$RUNTIME/lib" "$OUT/native_stream_smoke_v1" "$MODEL" "$WAV" \
  > "$OUT/events.jsonl" 2> "$OUT/native.stderr.log"
```

The future bounded controller must enforce the disk/output limits and preserve
timeout or crash attempts. Compile validation, malformed-WAV tests and actual
model execution have not run. Model pins and remaining ARM64 acceptance checks
are in `ARM64_FUNCTIONAL_VALIDATION_PLAN_V1.md`; live CM5 checks stay deferred.
