# ARM64 harness compilation and input rejection

`build_native_stream_smoke_v1.py` compiles the existing six-case native harness
against the pinned ARM64 C ABI and runs eight malformed-WAV cases under the
already installed QEMU. It never supplies a model. Passing this check proves
compilation, loader entry and early malformed-input rejection only; actual
saved-speech inference, Windows/ARM64 state parity and GUI integration remain
untested. It does not contact or validate the Pi.

Inputs: a fresh host admission with scope COMPILE_AND_MALFORMED_WAV_ONLY,
models_loaded=false, source_sha256, builder_sha256, header_sha256 and a short
expires_utc timestamp; the unchanged native_stream_smoke_v1.cpp, pinned native
header, existing Arm GNU 12.3 compiler/sysroot, packaged runtime and QEMU v2.
The host must first verify no active N4 worker, exact prior PID creation
identities, fresh ownership/census, C:50 GiB/G:75 GiB floors, 50-GiB payload
allowance and campaign cutoff. This script is not a substitute for host admission.

Outputs go only into a fresh private directory: INPUTS.json records tool hashes,
each command has bounded stdout/stderr and an exact Linux start identity,
the compiled ELF64 AArch64 executable, eight tiny malformed inputs, and RESULT.json.
One Linux CPU/nice10 and one child command at a time are used. Compilation is
bounded to 120 seconds; each rejection to 15 seconds; files to 1 MiB each and
total expected output to 32 MiB. No packages are installed or downloaded.
Keep failed attempts. The containing host invocation must also use a finite timeout.

After the existing supervisor has closed and the host admission is recorded,
PowerShell, CMD and Anaconda Prompt all use this same command. Change the output
suffix for a retry; never overwrite an earlier build:

```text
wsl.exe -d Ubuntu -- timeout --signal=TERM --kill-after=5s 300s python3 /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/build_native_stream_smoke_v1.py --admission /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/native-stream-build-v1-host/ADMISSION.json --output /mnt/g/Just_Peachy_N1/20260924_campaign/local/n5/native-stream-build-v1
```

Use no conda activation inside WSL. Success must be
PASS_ARM64_BUILD_AND_INVALID_WAV_ONLY, with all nine commands closed, compilation
exit 0 and eight exit-1 rejections. Inspect original logs if any command fails.
Do not launch this alongside a timed application collector. Keep the prior C++
source and its README unchanged; this companion documents the new build step.
