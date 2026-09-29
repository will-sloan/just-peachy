# A76 V3: isolate CPU weight repacking

Purpose: investigate the V6/V7 numerical mismatch without changing the reference tolerance or weights. In the retained ggml source, `GGML_USE_CPU_REPACK` registers an alternative CPU weight buffer. V3 removes that define from the V2 builder while retaining Cortex-A76 integer dot product and disabled FP16 arithmetic. This is a single build-option experiment, not an accepted speed improvement. All prior binaries and failures stay immutable.

Inputs: `build_cpu_a76_v3.py`, this README, a fresh `BUILD_ADMISSION.json`, and the previously verified scheduler-native-v1 source manifest, source and base library. The fresh target directory is `~/JustPeachy/research/nemotron-20260928/cpu-a76-v3`. The builder verifies hashes, boot ID, CPU affinity, expiry, memory/disk floors and the hard 768 MiB virtual-address bound. It compiles the same 14 CPU translation units sequentially. Outputs: BUILD_OWNER.json, BUILD_RESULT.json, command logs and the candidate library under output/. A separate V8 short/repeat/state test must compare probabilities against the unchanged generic V4 reference at max-absolute tolerance 1e-5. Build completion does not establish numerical equivalence, accuracy or real-time performance.

## PowerShell / Anaconda PowerShell

Inspect current Pi systemd jobs and exact boot/PID/start-tick identities first. After previous owners close, refresh the host and Pi storage/RAM census, create a new hash-bound admission (CPUs 2/3, one compiler, 600 seconds, 64 MiB output reservation, no downloads/GPU), and transfer the three input files using the strict SSH/scp identity in README.md. Do not reuse an expired or closed admission. Run:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-cpu-a76-build-v3 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/cpu-a76-v3/build_cpu_a76_v3.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command. No local activation is required. Keep >=850 MiB available RAM and >=5 GiB disk before dispatch. Preserve the existing application, global swap/OS settings and all old files. The kernel has no memory cgroup controller: RLIMIT_AS is a virtual-address cap, not an RSS or no-swap guarantee. Verify candidate hash and owner closure before V8.
