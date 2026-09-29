# B01 autonomous quiet artifact trial V1

Purpose: one fresh30-second native microphone stream trial with retained Sherpa/PnC + delayed Nemotron D1 + ReDimNet, compact journals and bounded float/PCM archives. This launcher binds AUTONOMOUS_QUIET_AUTHORIZATION_V1.json, not a user-ready assertion. No playback, requested speech, enrollment, accuracy scoring or changes to the installed app. Quiet/background input is not labelled silence.

Inputs: fresh window_guard_v5 host census; unchanged b01-artifact-fixture-v1/prototype and its independent partial model/PCM review plus separate copied-archive Save/Open pass; existing exact native model/library files; current explicit XMOSI2S ALSA/I2C configuration; hardware-only process-local ALSA configuration. The new app copy is byte-identical. Only its private live configuration evidence_dir changes to the run directory. Original hardware lease is retained. Before every launch verify exact baseline owners, boot, units, capture and both leases; device settings are snapshotted/read back/restored by the unchanged source route controller. No periodic reset.

Outputs: new exclusive b01-quiet-artifact-v1 target and private evidence directory, admission/source hashes/live unit properties, diagnostic fault flags/timestamps (rejected callback size is not upstream lost frames), private compact journals, exact float master and reopenable quantized PCM16 WAV, source/model/queue/closure receipts and withdrawn widget observations. Records remain private. Existing admissions, failed harness/source, user-only previews and all archives are immutable.

Limits:768MiB hard virtual,1MiB native/Python stacks, CPU2/3,total200%,one model thread,Tasks64,300second service/290alarm/10second stop;140second harness bound. Initial850MiB available RAM,5GiB disk plus output reservation. Sampled stops192MiB available or640MiB RSS; not hardRSS enforcement.128MiB combined new output reservation (64target+64host),8MiB hard per-file,4MiB service log. Compact event sink8MiB,1MiB logical record; bounded archive queue512items/4MiB; PCM960000frame ceiling per epoch. Actual source limit480000accepted16k samples/30seconds; input abort/overflow decisions unchanged. Kernel lacks MEMCG. This is not endurance or robust memory fit.

PowerShell (fresh census must be younger than15minutes; coordinator CPU14):

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/dispatch_b01_quiet_artifact_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V69.json'
```

CMD / Anaconda Prompt (uses existing environment, no package install):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\dispatch_b01_quiet_artifact_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V69.json
```

Run ID cannot be reused. --worker/--gate are target-only internal dispatcher modes. No --ready-now, spoken readiness or user-mode invocation is used. Back up all output to private host evidence and verify hashes; keep original target evidence. Independent success review must verify source/ASR/D1 coverage, ordered finite probabilities, exact PCM quantization/reopen, archive/event lineage and output limits, all queues/drain, natural process closure, route restoration/readbacks, capture closed and both leases released. Full numerical references for newly captured audio/E0 windows remain separate pending work. A handled failure must retain partial coverage and exact fault flags; it is not a successful full trial. The original app remains active, so timings are conditional. No physical display/touch or field release follows from withdrawn widgets.
