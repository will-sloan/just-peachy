# V5: full saved-source native D1 and resident repeat

Purpose: extend the independently reviewed 12-second V4 component smoke to the entire original 715,127-sample (44.6954375-second) saved file, twice with a resident reset. All source samples are retained. Model, adapter, profile, smaller-scheduler library and resource cap are unchanged. This is unpaced functionality/compute/resource evidence, not new DER/WER, real-world accuracy, original-1x-pacing or complete application acceptance. It tests a longer cache history and must independently pass the original frame/EOF/reset protocol. The existing app remains active, so timings are conditional diagnostics.

Inputs: retained V4 stage and bound assets plus fresh d1_smoke_v5.py, README_V5.md, INPUTS_V5.json and ADMISSION_V5.json. No files from earlier attempts are overwritten. Full nonempty output must have `715127 // 160 + 1 = 4470` frames and eight channels; endpoint support overhang is reported. Repeat equality tolerance stays 1e-5. Do not claim any unattempted case if the 600-second unit timeout or 768 MiB hard address-space bound ends execution.

Outputs: private OWNER_V5.json, RESULT_V5.json, saved_prefix_v5.npy (historical case label, now full source), resident_repeat_v5.npy and launch/memory-statistics log. Save independent unit termination evidence if native abort prevents RESULT finalization. Initial stage names remain historical; receipt scope and sample counts define the protocol.

## PowerShell / Anaconda PowerShell

After fresh resource/owner checks, copy the four new inputs to the retained d1-smoke-v3 directory with the verified SSH arguments in README.md. Then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-full-v5 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-smoke-v3/d1_smoke_v5.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the entire remote command. No local environment activation is needed. CPUs2/3, one native thread, available RAM850MiB, disk5GiB, no GPU/downloads/capture and no active-install changes remain. A long worker is not permission to start another numerical run beside it. Read its exact boot/PID/start ticks, unit state, admission and latest output first.
