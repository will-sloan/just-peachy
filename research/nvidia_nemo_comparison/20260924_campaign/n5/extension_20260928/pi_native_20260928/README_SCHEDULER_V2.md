# D1-only scheduler metadata capacity2048

Purpose: reduce virtual-address metadata reserved for D1 under the existing hard768MiB cap. The tested D1 geometry has reached870 graph nodes. Capacity2048 leaves more than twice that observed count; the original95% overflow rejection and warning guard are retained. This is a candidate until original source/repeat/reference/EOF passes. Do not bind this D1-specific runtime to Nemotron ASR without separate graph/resource qualification. The CPU lane-preserving library, model, weights and geometry remain unchanged.

Inputs: all hash-verified retained scheduler-native-v1 source/objects/static libraries, its immutable bundle manifest and build receipt, fresh build_scheduler_v2.py/README and BUILD_ADMISSION.json. The builder verifies every manifest input, accepting only the already recorded8192 session patch in that parent. It writes a separate session.cpp changing8192 to2048, recompiles that translation unit and relinks the28 retained objects. Parent files are never edited. Outputs: BUILD_OWNER/RESULT, new session/runtime/library and compiler/link logs, all private. A successful build is not functional acceptance or measured memory savings.

## PowerShell / Anaconda PowerShell

Stage in a fresh scheduler-native-v2 using strict SSH identity from README.md, after exact old owners/units close and a fresh target admission binding the script, README, parent bundle manifest and BUILD_RESULT. Reserve16MiB output within the existing combined allowance. Then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-scheduler-v2 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/scheduler-native-v2/build_scheduler_v2.py'
```

## CMD / Anaconda Prompt / Linux

Use double quotes around the SSH remote command for CMD/Anaconda Prompt. On Linux execute its systemd-run portion. No activation/install/download. Retain CPUs2/3, one compiler at a time, CPU200%,600seconds, Tasks64, hard768MiB address space, >=850MiB available and >=5GiB disk. Build inputs and outputs remain private; only this small source/README enter Git. Record exact boot/PID/start ticks and close the build before inference dispatch. Qualification uses a fresh derivative of the full-source/repeat harness at unchanged1e-5 generic-reference threshold, then combined application load/drain under the same cap. Never rerun expired admissions or overwrite failed evidence.
