# Continuous component RAM and backlog review

`review_soak.py` reads a completed, independently verified private native mirror.
It verifies every mirrored regular file again, then streams the bounded call
records without loading probability arrays or all timing records into RAM.
It creates ten-minute source-time bins for RTF, RSS, distinct cached PSS samples,
virtual memory, swap, available system RAM, task counts, CPU, temperature and
input/speaker backlog. Final drain computation is separate and also included in
a second RTF denominator. After the first warmup bin, descriptive slopes and
strictly increasing bin means are reported. They are not automatic leak or
steady-state diagnoses.

Input is the complete monitor directory, containing RESULT, MIRROR_COMPLETE,
MIRROR_MANIFEST and closed-output/benchmark. Output is a fresh private directory
containing early CPU14 REGISTERED_OWNER and SOAK_REVIEW.json. Existing output is
never replaced. The monitor's closure and whole-file hashes must agree.
No SSH, model, audio playback, recording or Pi mutation occurs.

A short run can check the reviewer but cannot qualify sustained operation.
This reviewer cannot turn a failed prefix, repeated single-speaker input, or
component-only inference into whole-app real-time or accuracy evidence.
A 4/8 GB benefit remains unmeasured. Thermal throttle flags were not recorded
by this benchmark; available temperature observations are retained.

PowerShell:

```powershell
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/review_soak.py" --monitor "$Q/COMPLETED_MONITOR" --output "$Q/FRESH_SOAK_REVIEW"
```

Command Prompt or Anaconda Prompt (the existing environment is explicit; no
installation or environment change is required):

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%N%\review_soak.py" --monitor "%Q%\COMPLETED_MONITOR" --output "%Q%\FRESH_SOAK_REVIEW"
```

Replace the placeholders with the actual completed monitor and a never-used
review directory. The active run must finish and close before review.
For launch and independent mirror commands see README_SOAK_DISPATCH.md.

The aggregation helper requires continuous call indexes and nondecreasing source
sample counts. It rejects incomplete JSONL records and nonfinite compute times.
Distinct PSS sample timestamps avoid counting one cached sample repeatedly.
Ten-minute bins use source time; slopes are per minute of represented audio and
are descriptive, not a claim about elapsed wall time or a causal memory leak.

