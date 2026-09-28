# Saved-file resident-model restart check

Purpose: test two complete source-paced EOF/Stop/Start cycles in one real
Controller, retaining the same loaded ASR and speaker models. This extends the
separately qualified lifecycle harness without editing its bound source.
It does not test microphone restart, early cancellation, endurance or the full
N4 twelve-pair protocol.

Inputs: exact lifecycle_v1.py hash, its admission tool, the shutdown derivative,
accepted CPU assets and the same saved PCM. Outputs: readable generated scripts
restart_lifecycle_v1.py and prepare_restart_v1.py, then a fresh private run with
two per-cycle sample/activity/stored-caption fingerprints, saved sessions,
phase/results and process-lifetime evidence. Exact parity is required; a timing
difference is preserved as failure rather than clamped or rescored. The reopen
process verifies both saved records and deletes only those test conversations.

The generator runs once and refuses existing destinations. Inspect its output
before admission. Actual runs retain the original 60-second inference drain,
240-second phase cap, 600-second total cap, 128-MiB output limit, two CPUs total,
GPU off and private desktop. ASR/speaker load counts must stay one with two
created streams. Every source sample must reach both inference lanes.

PowerShell from this directory, using the existing interpreter:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $prePiPython -B build_restart_harness_v1.py
# After reviewing generated source and verifying no active numerical owner:
& $prePiPython -B prepare_restart_v1.py --name a2-restart-v1 --backend nemotron_600m
# Only after completion, review and exact owner closure:
& $prePiPython -B prepare_restart_v1.py --name a0-restart-v1 --backend nemotron_hybrid
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B build_restart_harness_v1.py
"%PREPI_PY%" -B prepare_restart_v1.py --name a2-restart-v1 --backend nemotron_600m
rem After the first run has closed and been reviewed:
"%PREPI_PY%" -B prepare_restart_v1.py --name a0-restart-v1 --backend nemotron_hybrid
```

No visible app, device, personal store, capture, playback, training or Pi access.
Prepared code or a terminal result alone is not independent qualification.
