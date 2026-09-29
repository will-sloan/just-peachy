# Native B05 process-local startup stack reservation

Purpose: exercise the actual shared controller's early Stop, worker drainage and a subsequent full-file restart in the same process. This reuses the qualified anonymous Sherpa/punctuation plus delayed Nemotron source and model files without modification. There is no ReDimNet load, personal naming, microphone, playback, GUI or accuracy scoring.

Inputs: a fresh comprehensive host census, the independently reviewed `b05-anonymous-full-v1` target admission and source, its original 44.6954375-second saved PCM, and existing installed assets. Stop is requested after at least 128000 source samples (8 seconds); the second session must restart at source offset zero. Neither source file nor silence is shortened or skipped during the second session.

The dispatcher checks exact boot/PID/start identities, closed previous jobs, source hashes, storage and RAM, and creates a new target admission. Existing 768 MiB hard virtual address cap, CPUs 2/3, total CPU quota 200%, one native thread, 64 tasks, 180-second service bound and 140-second harness bound remain. At least 850 MiB available RAM and 5 GiB disk are required. The original rc5 app remains active. This is a new protocol; earlier full-file passage alone does not establish Stop/restart or robust memory fit.

Outputs: private `b05-native-stack-v1-evidence` host preflight/launch receipts; target `b05-native-stack-v1` admission, owner, two session journals, early Stop receipt, snapshots, memory samples and RESULT. A native abort may omit RESULT; preserve it as failure. Terminal collection is not acceptance. Independently inspect both sessions for source/ASR/D1 coverage, clean queues/handles/workers, no inference errors, separate epochs, full-restart 4470x8 probability parity at the unchanged 1e-5 gate, and natural process closure. Early-prefix probabilities are not compared with the full-file reference because EOF context differs.

## Run

Run once per immutable run ID. Do not reuse or overwrite an existing directory. Obtain a current host census with the extension window guard first. The paths below name the census prepared for this attempt.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b05_native_stack_v1.py --run-id b05-native-stack-v1 --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V16.json
```

CMD or Anaconda Prompt (explicit interpreter; no environment installation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b05_native_stack_v1.py --run-id b05-native-stack-v1 --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V16.json
```

The dispatcher uses verified SSH and a hidden bounded systemd service. Do not invoke the target harness directly outside its target admission and quota. New variants need fresh names, source bindings, review and instructions.

This new test applies systemd LimitSTACK=1048576 before starting Python, verifies both RLIMIT_STACK limits and glibc pthread default stack size are 1 MiB, and retains the existing Python setter-only 1 MiB stacks. It does not change OS/boot/global settings or raise the 768 MiB virtual-address cap. Earlier Python-only stack changes did not establish native defaults. The existing independently reviewed LRU1 runtime and application code are unchanged; a fresh copied catalog binds this process policy and new manifest. Source/sample/parity/closure gates are unchanged, including Stop and full restart. This is a stack-depth compatibility and memory observation for the tested workload, not general stack-safety or production qualification. Missing libc inspection symbols or a mismatched default fail before model loading.
