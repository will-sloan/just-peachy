# B01 V9: bounded process-local glibc allocation thresholds

V8 passed native model setup but aborted on an8MiB graph-metadata request at765.05MiB virtual size and512.70MiB RSS. The8MiB metadata runtime independently matches the full reference/repeat; this remaining combined address-space failure is preserved. V9 retains all V8 source, model, library, geometry, stack and hard limits, while setting MALLOC_MMAP_THRESHOLD_=131072 and MALLOC_TRIM_THRESHOLD_=131072 alongside MALLOC_ARENA_MAX=1 for this process only. The hypothesis is that returning large freed allocations and avoiding dynamically enlarged heap thresholds reduces unused address reservations. This may add allocation/system-call cost and is not a claimed speedup or proof of physical-memory fit.

Inputs/outputs/prerequisites are those of README_B01_METADATA_V1.md with fresh b01-short-v9, b01_native_short_v9.py/README and admission binding the exact three environment settings. No global glibc/OS/swap setting changes, no new model, downloads, live audio, enrollment or accuracy score. Independently verify actual source/ASR/identity passage, explicit backend and finalization/worker/file closure; do not credit process disappearance after a native abort as clean application closure.

## PowerShell / Anaconda PowerShell

After fresh target resource/identity/owner checks and input-bound admission:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-b01-short-v9 --wait --pipe --setenv=MALLOC_ARENA_MAX=1 --setenv=MALLOC_MMAP_THRESHOLD_=131072 --setenv=MALLOC_TRIM_THRESHOLD_=131072 -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-short-v9/b01_native_short_v9.py'
```

## CMD / Anaconda Prompt / Linux

Use double quotes around the remote command in CMD/Anaconda Prompt; Linux runs systemd-run directly. Keep CPUs2/3,CPU200%,Tasks64,180seconds,one model thread,hard768MiB virtual space,>=850MiB available,>=5GiB disk,16MiB output reservation. No activation/install/download. The original rc5 app remains active and unchanged. Success would qualify only this short saved-file functional/resource scope; full-file, Stop/restart, user-facing modes/GUI/storage, sustained real-time and real-life speech remain separate gates.
