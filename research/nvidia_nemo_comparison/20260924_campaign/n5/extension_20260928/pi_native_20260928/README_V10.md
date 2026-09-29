# V10: full-source/repeat with lane-preserving ARM dot product

Purpose: extend independently reviewed V9 short parity to the original complete source and resident repeat. V9 probabilities matched the generic V4 arrays exactly, with the original 1e-5 tolerance retained. The generic V5 full first pass exists and is valid; its repeat timed out at 600 seconds. V10 uses that preserved full first-pass array as reference and the same 600-second overall bound. The V5 failure remains. A shorter clip cannot replace this protocol.

Inputs: fresh `~/JustPeachy/research/nemotron-20260928/d1-a76-full-v10`, unchanged 715127-sample/16000Hz source (44.6954375seconds), mixed-Q8 D1 model, adapter and scheduler; CPU library from cpu-a76-v4; generic V5 full first-pass array as reference_generic.npy; d1_smoke_v10.py, this README, INPUTS_V10.json and new ADMISSION_V10.json. Use verified hashes and closed owners. Outputs: OWNER_V10.json, RESULT_V10.json, saved_full_v10.npy, resident_repeat_v10.npy and launch log. Review 4470x8 finite/ranged output, contiguous source frames, exact repeat/reset/empty/EOF/post-finish handling, max-absolute generic comparison <=1e-5 and exact closure. Retain any timeout with its completed partial evidence. No automatic retry or longer allowance.

This is a native component function/resource and arithmetic check, with the old installed app still active. It is not ASR/WER/DER, independently measured speech quality, integrated B01 acceptance, steady-state endurance or real-time qualification.

## PowerShell / Anaconda PowerShell

After V9 owner closure and a fresh target/resource check, stage a new hash-bound admission using the strict SSH/scp identity in README.md. Keep CPUs2/3, one native thread, hard768MiB virtual space, >=850MiB available RAM, >=5GiB disk, no GPU/download/capture. Run:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-a76-v10 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-a76-full-v10/d1_smoke_v10.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command. No local activation. Preserve prior stages, original app/autostart/data and OS/swap settings. Review results independently before any integration or profile promotion.
