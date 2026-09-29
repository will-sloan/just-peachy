# B01 V7: one process-local allocator arena

V6 still aborted requesting64MiB before printing scheduler initialization. Its last saved observation was722,688KiB virtual/443,024KiB RSS with20threads under the768MiB hard address-space cap. The scheduler2048 component is separately qualified but cannot solve an earlier allocation by itself. Preserve V6's abort and absent finalization. V7 changes only MALLOC_ARENA_MAX from2 to1 for the new application process, retaining1MiB Python stacks, exact shared-app-v2, qualified scheduler/CPU libraries and all limits/inference/drain gates. A single arena can introduce allocator contention; it is a memory hypothesis requiring measured passage and resource checks, not an assumed speedup.

Inputs/outputs: same as README_B01_SCHEDULER_V1.md, using fresh b01-short-v7, b01_native_short_v7.py/README, empty data with unchanged native binding/prefix and fresh admission with allocator_environment.MALLOC_ARENA_MAX="1". No code/model/recipe/cap is relaxed. Preserve original rc5 app/data and all failed evidence. Independently verify actual caption/source/identity passage and clean worker/handle closure. No GUI, accuracy, new live route or complete release qualification.

## PowerShell / Anaconda PowerShell

After fresh boot/exact-owner/unit/storage/RAM/input checks and target admission:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-b01-short-v7 --wait --pipe --setenv=MALLOC_ARENA_MAX=1 -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-short-v7/b01_native_short_v7.py'
```

## CMD / Anaconda Prompt / Linux

Use double quotes around the remote command in CMD/Anaconda Prompt; Linux runs systemd-run directly. No activation/install/download. Retain CPUs2/3,totalCPU200%,Tasks64,180seconds,one model thread,hard768MiB virtual space,>=850MiB available,>=5GiB disk and16MiB output reservation within the combined allowance. Record MEMORY.jsonl immediately and native logs; do not mistake a shell exit or process disappearance after abort for application finalization.
