# Native B05 Stop/restart V2: remove harness retention

Purpose: exercise the actual shared controller's early Stop, worker drainage and a subsequent full-file restart in the same process. This reuses the qualified anonymous Sherpa/punctuation plus delayed Nemotron source and model files without modification. There is no ReDimNet load, personal naming, microphone, playback, GUI or accuracy scoring.

Inputs: a fresh comprehensive host census, the independently reviewed `b05-anonymous-full-v1` target admission and source, its original 44.6954375-second saved PCM, and existing installed assets. Stop is requested after at least 128000 source samples (8 seconds); the second session must restart at source offset zero. Neither source file nor silence is shortened or skipped during the second session.

The dispatcher checks exact boot/PID/start identities, closed previous jobs, source hashes, storage and RAM, and creates a new target admission. Existing 768 MiB hard virtual address cap, CPUs 2/3, total CPU quota 200%, one native thread, 64 tasks, 180-second service bound and 140-second harness bound remain. At least 850 MiB available RAM and 5 GiB disk are required. The original rc5 app remains active. This is a new protocol; earlier full-file passage alone does not establish Stop/restart or robust memory fit.

Outputs: private `b05-stop-restart-v2-evidence` host preflight/launch receipts; target `b05-stop-restart-v2` admission, owner, two session journals, early Stop receipt, snapshots, memory samples and RESULT. A native abort may omit RESULT; preserve it as failure. Terminal collection is not acceptance. Independently inspect both sessions for source/ASR/D1 coverage, clean queues/handles/workers, no inference errors, separate epochs, full-restart 4470x8 probability parity at the unchanged 1e-5 gate, and natural process closure. Early-prefix probabilities are not compared with the full-file reference because EOF context differs.

## Run

Run once per immutable run ID. Do not reuse or overwrite an existing directory. Obtain a current host census with the extension window guard first. The paths below name the census prepared for this attempt.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b05_stop_restart_v2.py --run-id b05-stop-restart-v2 --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V14.json
```

CMD or Anaconda Prompt (explicit interpreter; no environment installation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b05_stop_restart_v2.py --run-id b05-stop-restart-v2 --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V14.json
```

The dispatcher uses verified SSH and a hidden bounded systemd service. Do not invoke the target harness directly outside its target admission and quota. New variants need fresh names, source bindings, review and instructions.

V1 preserved an actual native out-of-memory failure at 42.34 seconds of the restart. It also held a strong reference to the first stopped engine while accumulating full telemetry snapshots. V2 releases that test-only reference after saving the Stop receipt and retains compact progress counters, with a weak reference to observe lifetime without retaining the object. It does not force garbage collection, change the application, clear native cache or raise the cap. It keeps all sample, reference, error and closure gates. This is an independently admitted diagnostic of harness retention, not a claim that V1 was solely a test artifact.
