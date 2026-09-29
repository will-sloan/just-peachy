# V6: native A76 short protocol and generic probability comparison

Purpose: repeat the unchanged 12-second/resident-repeat/EOF test using the native Cortex-A76 CPU library. The full generic V5 first pass took358.232seconds (RTF8.015) for44.695seconds, and its repeat hit the600second overall bound. That failed full protocol is preserved; V6 is a separately bounded short diagnostic, not a replacement pass for it.

Inputs: fresh `d1-a76-short-v6` directory; unchanged model/source/adapter; copied V4 runtime with only libggml-cpu.so.0.12.0 replaced by SHA256`2133956eecdcdb3eb5ea0f5d440ff598befa5204700f94cdd60a1beba74eb089`; retained V4 first probability array as reference_generic.npy; V6 code/README plus INPUTS_V6.json and ADMISSION_V6.json binding every regular input. The native build emitted876 `sdot` instructions and verified1,954 retained source files. This is compiled-code evidence, not acceleration evidence.

Output: OWNER_V6.json, RESULT_V6.json, two `_v6.npy` arrays and launch/memory log. The original state/coverage checks stay intact. After model close, compare the first array to the generic V4 reference with maximum absolute tolerance1e-5, declared before dispatch in README_A76.md. Preserve an excess as a numerical-parity failure and investigate it; do not relabel saved-audio comparison as ASR/WER/DER accuracy. Quantify performance only with scope, resource/thermal/contention caveats; no full integrated mode is qualified here.

## PowerShell / Anaconda PowerShell

Stage the exact files under fresh target admission after build owner closure, using verified SSH/scp arguments in README.md. Then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-a76-v6 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-a76-short-v6/d1_smoke_v6.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command. No Windows environment activation is required. Preserve CPUs2/3, one model thread,768MiB hard virtual address space,850MiB available RAM and5GiB free disk before dispatch; no downloads, GPU, live capture or original-install changes. Keep numerical workers sequential and independently review outputs and exact closure.
