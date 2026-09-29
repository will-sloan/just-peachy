# Native delayed D1 with an independent1x saved-source producer

Purpose: measure actual input pacing, FIFO waiting and EOF drainage for the whole delayed recipe that passed full-source/repeat and exact generic/A76 agreement. This tests a real separate producer thread and one ordered native model stream on CM5. It is a component simulation, not integrated ASR/E0, live audio, independent real-life evidence or an accuracy score.

Inputs: same44.6954375-second saved WAV, pinned Q8 model, prepared native-profiles-v2 adapter, qualified2048-node/8MiB D1 metadata library and lane-preserving A76 kernel. The generic delayed reference and optimized delayed review must already be present and verified. All715127 samples are retained. No silence gating, playback, recording or downloads.

`d1_geometry_paced_v1.py` is a fresh derivative of the unpaced geometry harness. A producer thread follows absolute original1x source time, placing100ms source intervals in a FIFO of at most200 entries (20seconds). It supplies indices into the retained saved audio without duplicating PCM. Queue overflow fails explicitly; it never silently drops or truncates samples. Native model calls remain ordered on the main thread. The producer uses a1MiB stack setter only and must join cleanly. Original rc5 app remains unchanged. Two complete sessions exercise resident repeat and the same state/EOF gates as the unpaced check.

Outputs are private: source scheduling/actual-arrival records, per-call source/frame/availability trace, maximum queue depth/wait, source scheduling lateness, first-output wall time, total model-call cost, elapsed time and EOF drain, arrays/RESULT and independently verified REVIEW. Total elapsed/audio RTF includes waiting for the source and drainage; use summed model-call time/audio for inference workload. First output is speaker-probability availability, not a committed named-speaker label or transcript latency. A short paced pass does not establish30/60minute stability or dense-conversation quality.

`dispatch_geometry_paced_v1.py` stages fresh bindings and enforces the same strict SSH identity, exact owners, fresh host census/target admission, output budgets and768MiB virtual cap as dispatch_geometry_v2.py. It only accepts the qualified delayed A76 combination and its reviewed generic reference. No1GiB test is implied or authorized. `review_geometry_paced_v1.py` independently verifies source scheduling, FIFO residence, producer closure, complete samples/frames and exact reference/repeat arrays, and stores a stage-specific receipt.

## PowerShell

From this report directory, after a fresh host census:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_geometry_paced_v1.py --profile native_v3_delayed --kernel a76 --run-id d1-geometry-delayed-paced-v1 --reference d1-geometry-delayed-generic-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V6.json'
& $py review_geometry_paced_v1.py --run-id d1-geometry-delayed-paced-v1
```

Only review after terminal execution and exact owner closure. Existing run IDs and reviews must not be overwritten. Refresh census after15minutes rather than removing that guard.

## CMD / Anaconda Prompt

Use `cd /d` to this directory, then:

```cmd
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" dispatch_geometry_paced_v1.py --profile native_v3_delayed --kernel a76 --run-id d1-geometry-delayed-paced-v1 --reference d1-geometry-delayed-generic-v1 --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V6.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" review_geometry_paced_v1.py --run-id d1-geometry-delayed-paced-v1
```

The existing interpreter requires no activation/install. Target execution uses the installed rc5 Python under systemd-run/taskset: CPUs2/3, totalCPUquota200%,one native model thread plus the waiting producer,TasksMax64,600seconds,hard768MiB RLIMIT_AS,>=850MiB available RAM,>=5GiB disk. Reserve16MiB under the combined1GiB allowance; no OS/swap/current-app changes. See README_GEOMETRY_V2.md for ancestry and recipe details. Preserve all failed attempts and original acceptance gaps.
