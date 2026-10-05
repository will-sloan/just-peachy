# Exact job07 closure and private output copy

Purpose: retain the generic 256 MiB job monitor limit and add only the already
issued build20 `classic-ui-check-07` contract's independent 512 MiB copy allowance.
The exact unit, package SHA, helper SHA and finite issued interval are required.
This reads closure and copies output; it cannot launch, renew or signal a job.
The earlier failed monitor01 is preserved. Only `job_limits` changes in each
derived monitor/probe; source backups and independent restores precede use.

Inputs: original parent-directory monitor/probe and private job07 JSON. Outputs:
`job07_closure` scripts, private `audit-preparation/job07-closure-UUID` review,
then a fresh private monitor directory containing exact closed output files.
This job output copy is separate from permanent saved-session audio offload.

PowerShell, from this directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\prepare_job07_closure.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\job07_closure\monitor_native_job.py --job 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/classic-ui-check-07-JOB.json' --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/classic-ui-check-07-monitor-02' --poll-seconds 30 --copy-deadline-seconds 150
```

CMD and Anaconda Prompt: use the same arguments, double-quote the executable and
paths, and omit `&`. Preparation uses CPU14 /2 MiB /600 seconds with an early host
owner. Monitoring retains CPU14, strict SSH, 15-second native read-only alarms,
128 MiB address space, 1 MiB stacks, complete SHA/readback and existing free-space
floors. If a named output already exists, preserve it and use a fresh suffix.
