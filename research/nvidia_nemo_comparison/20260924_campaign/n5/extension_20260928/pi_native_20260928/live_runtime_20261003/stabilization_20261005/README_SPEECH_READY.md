# Owned speech readiness status

`monitor_speech_ready.py` makes one read-only status probe of an already owned
`classic-ui-check-N` job. It cannot start capture, models or a new job and cannot
mirror output. `native_speech_ready_probe.py` preserves the original exact
unit/boot/invocation/output-root binding and bounded systemctl child receipts,
early native owner, CPU3/128MiB address space/1MiB stack/FSIZE0/15-second alarm.
The host preserves CPU14 registration, strict SSH, bounded readers/writer,
natural SSH reap and a separate exact utility PID absence check.

Inputs: existing private `JOB.json` and a fresh private output directory. The
probe binds the job's exact `DRIVER_SETTINGS.json`, its actual-worker-started
action and request SHA, canonical launch, worker SESSION UUID and selected live
policy. It reads only that session's indexed metadata/count and one physical
source STARTED event from the existing database in read-only/query-only mode,
with bounded cache and SQL operation count. It checks source and worker actual
PID/start/boot identities and membership in the same owned systemd cgroup. It
does not request broad current pipeline or memory snapshots, captions or audio.

Output `status.speech_ready.ready=true` and `READY_ACCEPTING_LIVE_AUDIO` requires
the service active, source and worker alive in the owned cgroup, the actual
physical STARTED packet, an active recording with positive committed processed
sample count and a commit no older than five seconds. This establishes actual
recently accepted live audio, not working ASR, named identity, accuracy or
sustained real-time performance. Compare successive positive sample counts if a
second observation is needed. Waiting states distinguish worker/session/source
startup; source closure or failure does not become READY. Every observation is
one-use and ends with its own native/SSH closure receipts.

## Commands

The root operator must first complete the current native preread/guard and keep
the user's speaking window coordinated. This command only observes a job which
has already been explicitly admitted and started. Choose actual JOB path and a
fresh output label; it never launches `classic-ui-check-13` itself.

PowerShell:

```powershell
$speechSource = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$speechSource\monitor_speech_ready.py" --job 'G:\path\to\owned\JOB.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\speech-ready-check13-01' --status-only
```

CMD or Anaconda Prompt:

```bat
set SPEECH_SOURCE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SPEECH_SOURCE%\monitor_speech_ready.py" --job "G:\path\to\owned\JOB.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\speech-ready-check13-01" --status-only
```

Outputs: actual host `REGISTERED_OWNER`, exact source/job `.backup` and independent
`.restore`, `SOURCE_CLOSED`, per-probe early `NATIVE_OWNER`, status and natural
`SSH_CLOSURE`, and final `RESULT.json`. Failure preserves early owner/raw phase
diagnostics and marks uncertified. `--sample-memory` rejects; all monitor calls
are forced status-only regardless of that flag. Current source guard limits,
40-second SSH phase, 15-second native alarm and 65,536-byte job cap stay intact.
