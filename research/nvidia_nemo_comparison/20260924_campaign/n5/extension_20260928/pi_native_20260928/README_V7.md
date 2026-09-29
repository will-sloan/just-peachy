# V7: A76 dot-product candidate without FP16 arithmetic

Purpose: rerun the unchanged V6 short/repeat/EOF and generic-probability protocol after the single CPU-build flag change described in README_A76_V2.md. The V6 maximum error0.0114863 failed the declared1e-5 threshold; that failure remains. V7 retains the same threshold, input source, model precision, profile, smaller scheduler, one model thread and generic V4 reference. This isolates the candidate floating-point arithmetic change while retaining integer dot product. It is not ASR/WER/DER scoring or independent real-life quality validation.

Inputs: fresh `~/JustPeachy/research/nemotron-20260928/d1-a76-short-v7`; unchanged model/source/adapter/reference; a copied V6 runtime with only the CPU library replaced from the hash-bound successful cpu-a76-v2 build; V7 script, this README, INPUTS_V7.json and ADMISSION_V7.json. Verify actual binary hash from BUILD_RESULT.json before admission. No prior runtime is edited. Outputs are OWNER_V7.json, RESULT_V7.json, two `_v7.npy` files and the launch log. Independently verify shapes/ranges/repeat/parity, input hashes and exact process closure. If short parity passes, full-source/repeat and integrated/backlog gates still remain.

## PowerShell / Anaconda PowerShell

After fresh resource checks and cpu-a76-v2 owner closure, stage the exact inputs with the verified SSH/scp key/host arguments in README.md, then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-a76-v7 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-a76-short-v7/d1_smoke_v7.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command. No local activation/install. Preserve CPUs2/3,768MiB hard virtual-address cap,850MiB available RAM,5GiB disk,600seconds, GPUoff, no download/live capture and unchanged existing app/data. Short timings remain conditional because the old app is active; no real-time mode or long-session capacity is established by this check alone.
