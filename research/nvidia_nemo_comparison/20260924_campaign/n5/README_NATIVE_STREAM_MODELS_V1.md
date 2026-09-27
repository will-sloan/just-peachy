# Bounded ARM64 native ASR checks

These scripts run the already compiled `native_stream_smoke_v1` with accepted
N3 A2 and A3 model hashes and one unchanged saved mono 16-kHz input. This is a
QEMU ARM64 component check. It cannot accept N4, validate the shared GUI or
establish CM5 memory, real-time performance, installation or hardware readiness.
No Pi, microphone, playback, training or new enrollment is used.

`run_native_stream_models_host_v1.py` is the Windows worker launched through the
existing supervisor. `run_native_stream_models_v1.py` owns each Linux process
group. `native_stream_review_v1.py` independently checks the six JSONL cases,
source counts, closed streams, final text/word parity and closed recognizer.
The actual input text/logs and weights stay in private evidence, outside Git.

Inputs: a fresh immutable precheck with scope EMULATED_NATIVE_ASR_COMPONENT_ONLY,
admitted_utc, expires_utc, the complete resource census/projection, exact closed
prior owners, code bindings, build_result/binary bindings, audio binding and
frames, and ordered A2/A3 model asset bindings. The existing build RESULT must
pass compilation and eight malformed-WAV cases. The worker rechecks all source,
runtime, model and input hashes, supervisor PID creation identity and exact argv.
Use accepted N3 configs and the admitted N4 source-plan audio binding. Do not
resample, crop, change gain or feed reference labels to the executable.

Limits: host CPU 14/BelowNormal; one Linux CPU/nice 10, one model at a time,
thread settings 1, GPU disabled, 1,800 seconds per model, 3,750-second outer
Linux timeout, 128 MiB allocation, 16 MiB per file and 8 GiB virtual-address
screening ceiling. That ceiling includes QEMU and is not a device-fit result.
Each model has an exact Linux PID/start tick and independent process group.
Disk floors C:50 GiB/G:75 GiB and allocation size are checked during execution.
Cancellation/timeout terminates only that owned process group and stops the
remaining model queue. An ordinary closed model error is retained before A3.
All runs must expire before the unchanged September 28 02:48:19 UTC reserve.

Outputs: Windows ADMISSION/STARTED/RESULT and bounded logs; Linux INPUTS,
per-model command identities/logs/results, and RESULT. Failed/incomplete cases
stay failed. A successful result is PASS_EMULATED_NATIVE_ASR_COMPONENTS_ONLY;
it still has GUI_validated=false, N4_accepted=false, N5_complete=false and
CM5_tested=false. Subsequent review must check both Linux command groups empty,
normal exit 0, two independent parser passes, and exact Windows owners closed.

## PowerShell

Run the model-free checks before any numerical worker owns resources:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import sys; sys.path.insert(0,'../n4'); from metric_process import pin; pin(); import unittest; unittest.main(module='test_native_stream_review_v1',verbosity=2)"
```

After a fresh full census proves no active N4 allocation or other numerical
owner, write the precheck under private local/n5 and an immutable worker spec.
Its argv is the qualified Python executable, `-B`, the absolute host script,
`--precheck <fresh CHECK.json> --output <fresh private host directory>`; cwd is
this n5 directory. Use `supervisor.start` through its existing interface. Never
launch the Linux entry point beside an active timed application run. Inspect
the exact spec before starting, and use a new suffix on every retry.

```powershell
Get-Content '..\..\..\..\..\local\n5\native-stream-models-v1-worker.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import sys; from pathlib import Path; sys.path.insert(0,'../n4'); from metric_process import pin; pin(); sys.path.insert(0,'../supervision'); import supervisor; print(supervisor.start(Path('../../../../../local/supervision').resolve(),Path('../../../../../local/n5/native-stream-models-v1-worker.json').resolve()))"
```

## CMD / Anaconda Prompt

Use the same exact interpreter; no conda installation or activation is needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import sys; sys.path.insert(0,'../n4'); from metric_process import pin; pin(); import unittest; unittest.main(module='test_native_stream_review_v1',verbosity=2)"
type ..\..\..\..\..\local\n5\native-stream-models-v1-worker.json
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import sys; from pathlib import Path; sys.path.insert(0,'../n4'); from metric_process import pin; pin(); sys.path.insert(0,'../supervision'); import supervisor; print(supervisor.start(Path('../../../../../local/supervision').resolve(),Path('../../../../../local/n5/native-stream-models-v1-worker.json').resolve()))"
```

These start commands require a newly admitted spec/precheck; repeating an old
command cannot authorize a new run. The hourly campaign follow-up should inspect
local/n5/native-stream-models-v1/RESULT.json and linux/RESULT.json alongside the
shared worker heartbeat before further work. Do not edit bound scripts during
the run. A parser fixture pass is development evidence only.
