# A76 V2: retain dot product, disable FP16 arithmetic

The native A76 V1 short protocol completed state/reset checks and reduced12-second execution29.24→17.14seconds, but failed its previously declared generic-probability tolerance: maximum absolute difference0.0114863 versus1e-5. It is retained as a failed numerical-parity candidate, not a promoted speedup/release. FP16 arithmetic is a plausible source of the difference, not an established cause until isolated.

This fresh builder changes only CPU flags to `-mcpu=cortex-a76+nofp16` in the exact14-source build from README_A76.md. A target compiler macro probe confirms `__ARM_FEATURE_DOTPROD=1` while FP16 arithmetic macros are absent. Mixed-Q8 model weights remain unchanged. All hash verification, source/base library reuse, native compilation, instruction audit, bounds and failure preservation remain the same. This tests whether integer dot-product acceleration can be retained with generic-like floating-point behavior.

Inputs: build_cpu_a76_v2.py, this README, new BUILD_ADMISSION.json, the unchanged previous source manifest/source/base library. Stage is fresh `~/JustPeachy/research/nemotron-20260928/cpu-a76-v2`. Outputs are its own BUILD_OWNER/BUILD_RESULT, command logs and output directory. Require a separate short/full native comparison against the generic arrays at the unchanged1e-5 threshold; no ASR/WER/DER scoring. A build alone proves no improvement.

## PowerShell / Anaconda PowerShell

After all prior numerical/build owners close, transfer the three new files using the verified SSH/scp identity in README.md. Then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-cpu-a76-build-v2 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/cpu-a76-v2/build_cpu_a76_v2.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command. No local environment activation or new downloads. Keep one compiler at a time, CPUs2/3,768MiB hard virtual address space,850MiB pre-run available RAM,5GiB free disk and64MiB output reservation; do not alter or replace the current installed app or older libraries.
