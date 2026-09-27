# C-API diagnostic V3: verified Windows build reuse

Purpose: continue the paired Windows/emulated ARM64 investigation after V2
built successfully but refused an unadmitted compiler location. CMake selected
the installed Visual Studio Build Tools 14.43.34808 compiler instead of the
Community copy. V2 never ran inference. Its retained job forcibly closed the
owned compiler helper; the job and all observed identities are now absent.
The old admission, source and outputs stay unchanged.

V3 reuses the exact resulting x64 executable after verifying its actual compiler,
CMake compiler record, successful configure/build commands and their logs, three
source inputs and PE architecture. It copies the executable and two bound runtime
DLLs into a fresh private output and rehashes those copies. No compiler runs in
the new Windows model job. Linux still builds the unchanged V2 diagnostic source
with the preserved Arm compiler/header/runtime and runs one fresh full stream.
Model bytes, sample gain, decoding, precision and endpoint rules are unchanged.

`run_baseline_asr_diagnostic_v3.py` implements the build gate and owned children;
`run_baseline_asr_diagnostic_host_v3.py` is the supervised coordinator.
`test_baseline_asr_diagnostic_v3.py` checks reuse refusal boundaries without models.
The V2 reader tests also apply to the unchanged event format. See
`baseline_asr_diagnostic_v2/README.md` for the input measurements and four records.

## Inputs, outputs and limits

A fresh CHECK uses scope BASELINE_C_API_DIAGNOSTIC_ONLY_V3. It binds a complete
fresh resource census, 128-MiB output allocation, at most 30-minute expiry before
the September 28 02:48:19 UTC reserve, exact absent prior owners, the prior build
audit, actual Build Tools compiler, all old/new source dependencies, four model
assets, saved mono 16-kHz WAV/frame count and per-platform runtime/tool records.
`prior_windows_build_audit` must point to the preserved independent V2 audit.
Never reuse the expired CHECK or output directory from V2.

Outputs are a fresh ADMISSION, per-platform command/owner/build/measurement
receipts, private debug logs, Windows owned-job lifetime, Linux group closure,
per-platform REVIEW and terminal RESULT. Windows uses CPU4/BelowNormal in its
private job, coordinator CPU14, Linux one CPU/nice10/one math thread, GPU off.
Windows model cap is 90 seconds; Linux compile/model caps are 120/600 seconds.
Total limits, C:50/G:75-GiB floors and 128-MiB recursive output cap remain enforced.
No new downloads, device connection, GUI window, microphone, playback or training.

DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE means measurements finished; empty text is
still a failure for the original parity protocol. This diagnostic cannot certify
ASR state parity, application/GUI integration, target RAM or CM5 readiness. The
Pi stays off. Raw output and runtime/model/audio bytes remain outside Git.

## PowerShell

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest test_baseline_asr_diagnostic_v2 test_baseline_asr_diagnostic_v3 -v
# Only after fresh admission and matching explicit worker specification:
& $py -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-diagnostic-v3-worker.json
```

The specification argv is the qualified Python, `-B`, absolute V3 host path,
`--precheck CHECK_PATH --output FRESH_RUN_PATH`; cwd is this N5 directory. Only
the existing supervisor starts the host; never run internal children directly.

## CMD / Anaconda Prompt

Use the explicit interpreter without installing or activating an environment.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_baseline_asr_diagnostic_v2 test_baseline_asr_diagnostic_v3 -v
rem Only after fresh admission and matching explicit worker specification:
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-diagnostic-v3-worker.json
```
