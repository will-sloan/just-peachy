# V8: unchanged short protocol with CPU repacking disabled

Purpose: evaluate the A76 V3 candidate described in README_A76_V3.md. V8 changes only the candidate CPU library relative to V7; the short input, mixed-Q8 model, adapter, scheduler, low_latency recipe, generic V4 probability reference, one native thread and 1e-5 max-absolute tolerance remain unchanged. Saved audio is functional/resource evidence only. This does not measure ASR/WER/DER or real-life speech quality.

Inputs: fresh `~/JustPeachy/research/nemotron-20260928/d1-a76-short-v8`, the preserved model/source/adapter/reference, a separate runtime using the verified cpu-a76-v3 output, `d1_smoke_v8.py`, this README, INPUTS_V8.json and new ADMISSION_V8.json. Bind every file hash and verify the CPU build result. Outputs: OWNER_V8.json, RESULT_V8.json, saved_prefix_v8.npy, resident_repeat_v8.npy and launch log. Independently review shape/range, repeat, empty/reset/EOF/post-finish handling, reference error, unchanged inputs and exact owner closure. A short pass still requires full-source/repeat and integrated mode/resource gates.

## PowerShell / Anaconda PowerShell

After CPU build closure and fresh ownership/resource checks, stage exact inputs using the verified key/host arguments in README.md. Admit only CPUs 2/3, one native thread, hard 768 MiB virtual address space, >=850 MiB available RAM, >=5 GiB disk, 600 seconds, GPU off and no capture/download. Then run:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-a76-v8 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-a76-short-v8/d1_smoke_v8.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command; no local environment activation. Preserve the current app and all older evidence. Timings remain conditional while the old app runs. No terminal success qualifies an application mode or long conversation.
