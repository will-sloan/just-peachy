# V9: model check after preserving generic dot-product lanes

Purpose: run the unchanged 12-second/repeat/EOF/state/reference protocol with the candidate from README_A76_V4.md. Inputs remain identical to V8 except the CPU library and versioned harness/receipts. Max-absolute reference tolerance stays 1e-5; no ASR/WER/DER is calculated. This is saved-file software/resource validation, not independent speech quality.

Stage a fresh `~/JustPeachy/research/nemotron-20260928/d1-a76-short-v9` with the immutable model/source/adapter/reference, separate runtime with verified cpu-a76-v4 library, d1_smoke_v9.py, this README, INPUTS_V9.json and ADMISSION_V9.json. Outputs: OWNER_V9.json, RESULT_V9.json, two probability arrays and launch log. Independently verify all inputs, frame/range/repeat/reference checks and exact owner closure. Full-source/repeat and integrated application gates remain separate.

## PowerShell / Anaconda PowerShell

After build closure, fresh boot/PID/resource checks and a new admission, use the strict staging identity from README.md and run:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-a76-v9 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-a76-short-v9/d1_smoke_v9.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command; no activation/install. Keep CPUs2/3, one native thread, hard768MiB virtual space, >=850MiB available RAM, >=5GiB disk, 600seconds, GPUoff, no live input and no fallback. Preserve the old app, previous libraries, evidence and source. Timings remain conditional while the installed app is active.
