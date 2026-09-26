# Released sessions for a same-Controller restart

Purpose: implement the deliberate mid-file stop prerequisite for a later
same-Controller/UI restart test. `restart_source_capture.py` retains exact engine,
consumer, command-worker and model-store objects, observes the unchanged source,
and enqueues exactly one public `Controller.stop()` call. After the caller drains
commands, it captures a released session while the Controller remains open.
`restart_session_closure.py` checks that all delivered samples drained through
journals, ASR, event consumers, text writers, native finalization and the archive.
All earlier qualified helpers and frozen application code remain unchanged.

Inputs to the internal primitive: an independently admitted private-desktop
Controller, its unchanged eight-field full audio job, backend contract, frozen
source root, and explicit `mid_file_stop` or `completed_release` intent.
The first requires a positive prefix strictly shorter than the original file;
the second requires complete source delivery and drained owners before release.
The caller pumps the private GUI and waits for command completion. No direct
source stop, new pacing loop, model replacement or Controller close occurs here.
The source start observer still admits exactly one unchanged FileSource start.

Outputs, after release, in a fresh private directory: CAPTURE.json,
OBSERVATION.json and TRACE.bin. The original job and expected file length are
never shortened to represent a stopped prefix. `delivered_frames` is separate.
The closure capture takes the retained engine/consumer, source-clock observer,
original job, finished RestartSourceCapture object and its CAPTURE binding.
Its reader verifies the release binding and exact epoch, source-clock session,
terminal sample counts, empty queues, closed workers/handles and released model
lease. `validate_complete` also joins the archive to that session and delivered
count. Delivery and engine/archive reviews must both pass; neither alone proves
an actual restart pair, full uninterrupted continuity, timing, quality or N4.

The guarded development probe exercises the exact FileSource/MemoryJournal/
AbsolutePacer class bodies with synthetic RAM, time and threads. Fake Controller
commands exercise request/release and failures. Pure readers also use explicitly
synthetic owner facts and longer planned jobs joined to unchanged historical
terminal receipts. Saved test flags remain true; only copied pure-reader fixtures
normalize them. Runtime evidence containing test seams is rejected. No audio
file, model, Controller, GUI, device or Pi is started. The actual engine-capture
routine is not exercised on a new runtime here. A paired lifecycle coordinator,
exclusive-run integration and real two-session test remain required.

## Run in PowerShell

No installation is needed. The helper pins itself to CPU14 at below-normal
priority, one math thread and GPU off. Its private evidence allowance is 8 MiB,
with existing shared-budget, disk-floor and healthy-D1 checks. Preserve every
attempt and choose a fresh suffix when rerunning. Do not bypass phase gates.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_restart_session.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-session-probe-v1'
```

## Run in CMD or Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_session.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-session-probe-v1"
```

Probe inputs are the existing qualified application-delivery/source/closure code
and nine bound historical sessions. Outputs are PROBE_OWNER.json, source copies,
ADMISSION.json, tests.txt, two labeled synthetic review examples, and RESULT.json
or preserved FAILED.json. The 22 checks include partial/full dispositions,
duplicate starts/stops, wrong owners, pending commands, command exceptions,
foreign hooks, copied-source flags, tampered clocks/counts, raw trace corruption,
closed Controller, missing worker closure, foreign epochs and changed bindings.
Publish qualification only after the helper exits and all bindings still match.

The preserved v1 probe passed all 22 checks. A final review then made failed
captures report the actual Controller closed state and added rejection of false
restart/acceptance claims. Use a fresh `restart-session-probe-v2` directory for
the final checked version; retain v1 and its original source snapshots.
