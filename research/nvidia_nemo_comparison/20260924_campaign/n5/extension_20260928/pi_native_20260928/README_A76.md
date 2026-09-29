# Native Cortex-A76 CPU-kernel candidate

Purpose: rebuild only the 14 ggml CPU translation units with the CM5's observed ISA (`-mcpu=cortex-a76`) instead of generic `-march=armv8-a`. The source and model precision remain unchanged. The observed CPU supports NEON, FP16 and dot product; do not enable unobserved I8MM/SVE. No CUDA, Vulkan, OpenMP, KleidiAI or extra native model threads are added. This can enable faster kernels, but must not be described as a measured speedup until actual native comparison and numerical checks pass.

Inputs: `build_cpu_a76_v1.py`, this README, a fresh BUILD_ADMISSION.json and the already verified ggml source/base runtime under scheduler-native-v1. The builder verifies every retained ggml source hash against the original bundle manifest, expected base library hash, target boot/CPU features/affinity, admission expiry and resource floors. Source is read-only. It uses installed native GCC/binutils and directly compiles/links using the original 14-unit source list, ABI/feature defines, optimized release/PIC settings and SONAME/RPATH. Warning flags are simplified; semantics and one-thread behavior are unchanged. CMake's installed version is insufficient for a clean configure, so this is a reproducible partial rebuild, not a clean whole-project CMake build. No downloads are needed.

Outputs: fresh output objects/library, command logs, BUILD_OWNER.json and BUILD_RESULT.json with binary SHA256 and actual emitted `sdot`/`udot` counts. Large disassembly is not retained. All raw files remain private. At most one compiler child runs; it inherits the 768 MiB hard virtual-address cap and disabled core dumps. Systemd also bounds CPUquota200%, CPUs2/3, tasks64 and runtime600seconds. Keep target RAM850MiB available before dispatch, disk5GiB and output64MiB. Do not compile concurrently with a numerical worker under this initial admission.

## PowerShell / Anaconda PowerShell

After the current numerical owner is closed, copy script, README and fresh admission to `~/JustPeachy/research/nemotron-20260928/cpu-a76-v1` using the retained key/host arguments in README.md. The admission binds those files and the source-manifest SHA256. Run:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-cpu-a76-build-v1 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/cpu-a76-v1/build_cpu_a76_v1.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the entire remote command. No Windows environment activation is required. Use new output/unit names for retries and retain every failure.

## Required next comparison

Use a fresh runtime directory with only this CPU library replaced, alongside the separately verified smaller-scheduler library. Bind all binaries and source hashes. Run the same saved 12-second/full-source protocols and compare every probability to the generic-kernel candidate (initial maximum absolute tolerance 1e-5), source clock and all EOF/reset behavior. If parity exceeds the declared tolerance, preserve and investigate rather than silently accepting it. This numerical reproducibility check is not a DER/WER accuracy metric. Time both under the same thread/resource/chunk recipe and record contention, load, CPU/RSS, thermal/clock/throttle and swap. Only then test selected larger native recipes and integrated caption-first modes. Do not overwrite the current installation or call a compiled library a ready application.
