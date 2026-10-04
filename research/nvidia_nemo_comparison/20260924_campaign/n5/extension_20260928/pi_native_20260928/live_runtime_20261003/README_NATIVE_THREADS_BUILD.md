# Bounded isolated native two-thread build

`launch_native_threads_build.py` is an injected `host_operations.py` action.
It prepares a fresh native user service which compiles the exact prepared
one-to-two graph-thread source variant. It uses the retained compiler, header /
object archive and unchanged model ABI. It never loads a model or qualifies
performance. Source/default-one behavior is described in
[README_NATIVE_OPTIMIZATION](README_NATIVE_OPTIMIZATION.md).

Actual build evidence: `native-threads2-build-01` compiled on the CM5, with all
seven commands returning zero. The root operator verified owner4854/start836736
closed, its cgroup empty, and every regular output mirrored. The new core SHA is
`210fee955c8728935e28598bffaf618868a9b9d57b76ac124c753f594a6e0f4d`; descriptor SHA is
`3fdb0a0699e06a0608ca6cf5676676e3416bf291398271ebd3fd9a5bca41bc57`.
The build receipt's `native_execution=false` means **no model inference**;
the compiler and linker did execute natively. It must not be interpreted as a
host-only or simulated build. No inference/performance result follows from this.

The unchanged variant verifier subsequently passed against the actual mirrored
source/libraries/receipts and original pinned GGUF bytes through a read-only
Linux-to-host path mapping. No native library or model was loaded for that check.
Receipt: `live-runtime-20261003/presets-preparation-actual-variant-3b428d26042142b6b5b7d4eebe0f29f8/RESULT.json`
under the private PC root. Original native output remains immutable.

The action preserves previous builds, the retained native libraries and frozen
runtime packages. It compiles a fresh session object and an exact reproduction
of the retained LRU8 Sortformer object; recompiling that object avoids trusting
an unpinned loose object. Only these objects differ from the retained link recipe.
The Sortformer source, geometry, cache policy and model mathematics are unchanged
from the retained Chunk52 library. Parallel execution still needs numerical
comparison: bitwise identity is not promised.

## Inputs and native scope

The private payload has these fields:

| Field | Required value |
|---|---|
| `boot_id` | Actual current CM5 boot ID from fresh ownership inspection |
| `expires_unix` | Finite fresh expiry within600 seconds |
| `label` | Unique lower-case alphanumeric/hyphen label, 4–48 characters |
| `maximum_output_bytes` | `67108864` (64MiB native plus an independent64MiB PC mirror) |
| `source_sha256` | `9d83b3c063f7cd0c56362648f0b8f8b5a9962e884f9a533631074c59f47c895c` |
| `source_b64` | Base64 of the exact prepared `threads2/session.cpp`; <65,536 characters |

The action admits non-root CPU2/3, shared aggregate200%, Tasks64, AS768MiB,
stack1MiB, core0, per-file8MiB, CPU150seconds, alarm170seconds, unit180seconds
and stop grace15seconds. It verifies actual unit membership/properties, takes
the existing research and hardware exclusion locks, and requires850MiB available
RAM at admission, a192MiB runtime floor and5GiB disk floor plus full reservation.
The same four numerical-library environment values remain1. No SSH operation
was performed while preparing this action.

Retained native inputs are rooted under
`/home/peachyprototype/JustPeachy/research/nemotron-20260928`:

* `scheduler-native-v1/bundle.tar.json`, SHA
  `c1fab2b4a3041412add0a1243919600b442785e4a76be9e65aa9b5397f090066`.
  Every retained input is verified; only the already-patched scheduler source
  uses its known subsequent hash. The exact manifest contains 2,436 files and
  32,153,457 declared bytes; mismatched counts or bytes fail before compilation.
* The original runtime archive,27 retained ASR objects, and original Sortformer
  source are read from `scheduler-native-v1/inputs`. The28th object is rebuilt
  from the exact retained LRU8 source hash.
* The existing `g++ (Debian 12.2.0-14+deb12u1) 12.2.0` toolchain and retained
  compile/link flags are used. Version mismatch fails before compilation.
* The installed Chunk52 A76 library group is individually pinned before it is
  copied into the new isolated directory. There is no OpenMP rebuild.

Compiler diagnostics are streamed with a1MiB cap per command and a finite
command deadline. Owned command process groups are terminated on a diagnostic
overflow or timeout. No entire compiler output is collected into RAM.

## Outputs

The fresh output directory is
`live-runtime-tests-20261003/LABEL` under the native campaign root. It retains
`ADMISSION.json`, early `OWNER.json`, `wrapper.py`, both source files, bounded
command logs, `SOURCE_VARIANT.json`, `build/` objects/archive/core, `runtime/` isolated regular library
files, `BUILD_RESULT.json`, `RUNTIME_VARIANT.json`, `JOB_EXIT.json` and `JOB.json`.
All failed outputs remain preserved.

`RUNTIME_VARIANT.json` pins the new core and every reused dependency, explicitly
sets variant `chunk52-native-threads2`, geometry52/1/0/80/264/40, LRU8 and graph
thread request2, and marks native qualification false. It references existing
model bytes; it does not copy weights. The current normal binding intentionally
rejects unknown core hashes. Root integration must explicitly admit this exact
new variant descriptor after inspecting its build receipt, rather than weakening
the general core-pin check. The benchmark-only
[explicit variant verifier](README_NATIVE_VARIANT.md) provides that path once
the actual build and independent closed-file mirror have been reviewed.

Host preparation syntax-checked the action and its complete generated native
wrapper and passed the existing monitor's envelope validator. Receipt:
`live-runtime-20261003/presets-preparation-build-action-30c8f9f30b174ef0a4aaeba13c1dc5e8/RESULT.json`
under the private PC root. This did not compile or execute native code.

`JOB.json` uses the existing monitor's component-job envelope, with
`job_kind=native-thread-build`. Its legacy `package_manifest_sha256` refers to
the retained build-bundle manifest, and `package_manifest_kind` records that
meaning. It is not a runtime application-package claim. A launch receipt is not
build completion; independent exact owner/cgroup closure and complete hash-checked
PC mirroring are required before review or inference.

## PowerShell dispatch

Prepare the source with the CPU14/early-owner commands in
[README_NATIVE_OPTIMIZATION](README_NATIVE_OPTIMIZATION.md#host-only-source-preparation).
Root then constructs the above fresh private payload from the known source bytes
and actual current boot/expiry. Set `$n` to this code directory and replace the
private payload path. The existing host wrapper registers its owner, verifies
backup and current ownership, and reserves the independent copy before dispatch.

```powershell
$n='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$n/host_operations.py" --label thread2-build-launch-01 --action "$n/launch_native_threads_build.py" --payload 'G:/PRIVATE/FRESH_THREAD2_BUILD_PAYLOAD.json' --writes
```

Command Prompt / Anaconda Prompt:

```bat
set "N=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%/host_operations.py" --label thread2-build-launch-01 --action "%N%/launch_native_threads_build.py" --payload "G:/PRIVATE/FRESH_THREAD2_BUILD_PAYLOAD.json" --writes
```

Use the existing [job monitor](README_JOB_MONITOR.md) with the returned `JOB.json`
and a new64MiB private mirror allocation. Only the authorized root operator
dispatches/monitors this action. Do not run the action file directly: `PAYLOAD`
is provided by the verified injected-action wrapper.

## Required comparison after successful build

One fresh process must compare exact715,127 samples, all4,470×8 output values,
frame origins and EOF against the same retained Chunk52 reference. Keep the
original thread1 result immutable. Report max/RMS differences and changes in
decisions; a valid build alone provides no numerical equivalence. Measure init,
per-push/finish compute, mature-context time, task observations, CPU/wall, memory
and queue growth under the unchanged CPU2/3 shared200% envelope. Whole-pipeline
ASR/embedding competition remains a separate measurement. Current default1 and
all original sources/libraries remain unchanged.
