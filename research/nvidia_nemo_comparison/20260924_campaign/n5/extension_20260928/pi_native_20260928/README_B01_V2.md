# B01 V2: bound allocator arenas without increasing memory limits

V1 reached the actual shared controller and failed loading the Sherpa encoder with std::bad_alloc under the hard768MiB virtual-address cap, at peak206,209,024bytes RSS. Its controller closed cleanly and its failure remains. A successful standalone Sherpa run does not rule out address-space overhead when loading models on application worker threads. glibc arena reservations are the next hypothesis, not an established cause yet.

V2 keeps the exact source bundle, model/runtime files, input prefix, shared controller, selected B01/anonymous/balanced mode, one native thread/model, two admitted CPUs and all V1 inference/drain/memory limits. Its launch sets **MALLOC_ARENA_MAX=2 only for this new process**. No global allocator, OS or swap setting changes. The harness additionally records VmSize/VmPeak/RSS/thread counts at lifecycle boundaries. This is instrumentation, not an alternative inference implementation. Do not remove RLIMIT_AS if it fails.

Inputs: fresh `~/JustPeachy/research/nemotron-20260928/b01-short-v2`, b01_native_short_v2.py, this README, unchanged prefix12.wav, empty separate data containing only the hash-bound n2_runtime.json, existing verified shared-app-v1 source and model/runtime assets, and fresh ADMISSION.json. See README_B01_V1.md for bundle preparation, full inputs and scope. Outputs: OWNER/RESULT, FINAL_SNAPSHOT, PROGRESS and private application journals. Preserve all V1 files. Require exact owner closure and fresh RAM/disk checks before dispatch. Saved audio is function/resource evidence only; no accuracy scoring, capture, playback, enrollment or GUI window.

## PowerShell / Anaconda PowerShell

After staging and a new admission (CPUs2/3, CPU200%, tasks64,180s,hard768MiB virtual space,>=850MiB available RAM,>=5GiB disk,16MiB output reservation), run:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-b01-short-v2 --wait --pipe --setenv=MALLOC_ARENA_MAX=2 -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-short-v2/b01_native_short_v2.py'
```

## CMD / Anaconda Prompt / Linux

For CMD or Anaconda Prompt use double quotes around the remote command, with no activation/install. On the Pi use the systemd-run portion directly. This is a bounded test harness, not a user-ready launcher. Independently inspect captions, source/identity coverage, worker closure and resource evidence before crediting even the narrow integration check. Long-source combined pacing, GUI modes, save/reopen/delete and real-life speech/endurance remain separate.
