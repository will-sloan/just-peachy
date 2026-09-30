# Combined B01 with an isolated microphone process

Purpose: run the actual B01 Controller, Sherpa/PnC, delayed Q8 Nemotron diarizer and retained ReDimNet with the previously qualified isolated PortAudio source. This is the changed combined trial after the V53 source-only passage. No maintenance/reset, solicited speech, playback, enrollment or downloads. Quiet/background audio is private stream/resource evidence, not labelled silence or acoustic quality. New captured audio has no independent numerical model reference.

Inputs: byte-identical copy of b01-isolated-fixture-v1/prototype, its existing n2_runtime model manifest, installed live configuration, current autonomous authorization, reviewed source-quiet-v2 and recovery-v3 receipts. Existing shared model assets remain in place. Original config/install are copied and hash-verified before capture. The source factory fsyncs its readable route snapshot before setters, restores while retaining clock/lease, and verifies full post-route equality. Restoration targets the readable post-recovery state; unreadable pre-restart volatile state is not recoverable.

The new main module subclasses Controller only to supply explicit IsolatedLiveConfig; the per-process source subclass adds a bounded metadata/hash trace after acceptance. It uses qualified pipeline V2, facade V2, bridge V2 and transport V3 without changing their files. Actual source Stop retains queued accepted audio. Stop is requested at >=480000 accepted 16k samples (30 seconds); every tail is retained and counts may exceed480000. A512000-sample ceiling explicitly fails if exceeded; it is never a silent trim. Capture must reach30seconds within40seconds; overall main progress bound140seconds, child alarm90seconds, service300seconds with60seconds Stop allowance. No source-only replay or old ready-now flag.

Outputs: private admission, exact owners, live systemd envelope, sampled current process RSS/virtual memory, source TRACE (4MiB), child terminal ACK, source/route Stop receipts, compact application journals, float master and reopenable PCM, actual Save/Open and withdrawn Tk comparisons. Empty text is permitted and is not a silence label. Source/module/queue/controller closure, full ASR/D1 accepted-sample and EOF coverage, PCM and per-block hashes/clocks require independent review. A collection exit alone is not acceptance. Logs/artifacts remain preserved on failure.

Envelope: WINDOW_V5;64MiB combined new output (32MiB target/32MiB host backup),52GiB total target-inclusive payload with retained2.5GiB reservations,5GiB output window. Fixed32GBPi retains>=5GiB available; C>=50GiB/G>=75GiB. Main768MiB/child256MiB hard virtual,1MiB stacks,CPU2/3 shared200%,Tasks64,one model thread/GPUoff. InitialRAM850MiB; sampled aggregateRSS640MiB/availableRAM192MiB stops. No MEMCG/hardRSS claim. Per-file8MiB. Child ru_maxrss can include pre-exec parent history; current per-owner /proc samples are recorded separately. Baseline app remains active, so timings are conditional.

PowerShell (fresh unused census less than15minutes old):
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_b01_isolated_quiet_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V114.json
```

CMD / Anaconda Prompt (existing environment, no activation/download):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_b01_isolated_quiet_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V114.json
```

The main/envelope modules are admitted internal entry points, not standalone launchers. Dispatcher requires strict SSH, current owners/leases/budgets, copies and binds inputs before systemd execution, and refuses an existing run directory. Never rerun a closed admission. Preserve failed cases and independently back up all private outputs by hash. Finish before October1 17:47:34UTC.
