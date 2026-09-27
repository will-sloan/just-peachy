# Paired C-API diagnostic for the empty-output failure

Purpose: distinguish C-API/runtime/sample behavior from Python binding and
recognizer initialization order after the preserved baseline ARM64 V1 failure.
This is investigation only; an empty transcript may complete the diagnostic
but cannot earn component, state-parity, GUI or release acceptance.

`diagnostic.cpp` includes the unchanged V1 RIFF/stream implementation with its
main function renamed. It records Sherpa version/revision/date and decoded
float32 sample statistics, enables the C API's debug configuration output and
runs one complete saved source on a fresh recognizer. It omits V1's preceding
empty/short streams to isolate that ordering variable. Model bytes, gain,
one thread, endpoint rules, 1,600-sample pushes and 10,560-sample final padding
stay unchanged. FNV-1a of little-endian float bits is a diagnostic fingerprint,
not a cryptographic asset identity; the original WAV is separately SHA256-bound.

The same source is built with the installed Windows Visual Studio 2022/MSVC
14.43.34808 and with the existing Arm GNU 12.3.rel1 cross-compiler. Each build
uses that platform's verified installed/wheel C header and C API runtime.
The host runs Windows first in its owned private-desktop job, verifies normal
closure, then runs ARM64 under QEMU. It never shows a window or switches the
input desktop. The Pi stays off; no device, microphone, playback or training
API is used. Existing model/WAV files are read-only inputs.

## Inputs and outputs

The internal scripts are `../run_baseline_asr_diagnostic_v2.py` (Windows/Linux
child) and `../run_baseline_asr_diagnostic_host_v2.py` (supervised owner).
`CMakeLists.txt` only configures the Windows executable. The Linux child uses
the exact cross-compiler/sysroot/QEMU and three retained wheel members in the
previous failed run's INPUTS receipt; it does not copy or overwrite them.

A fresh CHECK JSON supplies scope BASELINE_C_API_DIAGNOSTIC_ONLY_V2, admission
and expiry UTC, 128-MiB output cap, a complete current resource census,
four exact closed prior owners, all source dependencies, WAV/frame count,
the encoder/decoder/joiner/tokens bindings, prior Linux INPUTS, CMake/cl.exe
bindings, Windows Sherpa root, and its header/import-library/two-DLL bindings.
Use the existing supervisor start interface within 120 seconds of admission.
Total allocation is at most 1,800 seconds and must end before the unchanged
September 28 02:48:19 UTC packaging reserve. No shared ledger is edited.

Windows coordination uses CPU14; the private diagnostic job and all compiler/
model children use CPU4/BelowNormal. CMake configure/build/model caps are
120/180/90 seconds; the host bounds the whole Windows phase to 420 seconds.
Linux uses one CPU, nice10, one math thread, GPU disabled, 120-second compile
and 600-second model limits. The inherited owned process-group helper preserves
PID/start-tick, command, exit and closure receipts; the outer WSL limit remains
1,450 seconds within the total admission expiry. C50/G75-GiB floors and the
recursive 128-MiB output cap remain monitored. QEMU's 8-GiB virtual-address
containment limit is not a target RAM measurement.

Outputs in a fresh private local/n5 directory are ADMISSION/LINUX_ADMISSION,
REFERENCE_OWNER and Windows job LIFETIME, exact command owner and exit logs,
compiler configuration, binary hashes, model.stdout/model.stderr, REVIEW and
terminal RESULT per platform. Debug/log text and WAV/model/runtime bytes stay
private. A diagnostic comparison checks sample fingerprints, effective config,
runtime identities, final counts and endpoint positions. Do not publish raw
transcripts. DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE means only that measurements
finished normally; keep the failed V1 protocol unchanged.

## PowerShell

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest test_baseline_asr_diagnostic_v2 -v
# Only after a fresh complete census and matching CHECK/worker specification:
& $py -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-diagnostic-v2-worker.json
```

The worker argv is the qualified Python, `-B`, absolute host script,
`--precheck CHECK_PATH --output FRESH_RUN_PATH`; cwd is the N5 directory.
Do not directly run internal children or reuse an expired admission/output.

## CMD / Anaconda Prompt

No activation, package installation or download is needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_baseline_asr_diagnostic_v2 -v
rem Only after fresh admission and previous-owner closure:
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-diagnostic-v2-worker.json
```

The three model-free tests cover missing input/records, incomplete delivery and
false acceptance/hardware claims. They do not test model correctness. A proposed
repair needs a new derivative and the original complete parity/state retests;
this diagnostic does not replace them or promote a backend to Pi-ready.
