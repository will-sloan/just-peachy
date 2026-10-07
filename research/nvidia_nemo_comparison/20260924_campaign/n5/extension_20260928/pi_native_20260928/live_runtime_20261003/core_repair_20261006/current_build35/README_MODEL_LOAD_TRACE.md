# Bounded model-load memory diagnosis

`model_load_trace.py` records memory before, during and after the unchanged
installed model loaders, including failure. `installed_engine.py` uses it around
Nemotron prewarm and ASR/punctuation/embedding setup, plus runtime-import and
cleanup checkpoints. It does not load models by itself, change inference settings,
capture audio, raise resource limits or claim physical process closure.

The native input is the current process's bounded `/proc/self/status`,
`smaps_rollup`, and `/proc/meminfo`, plus actual RLIMIT_AS and allocator environment.
Output is session `work/model_load_memory.jsonl`, capped at1 MiB with records at
most8 KiB. Sampling is once per second during each loader; boundary samples are
fresh. RSS/PSS and system available RAM are reported separately from VmSize and
VmPeak. Missing PSS access is null. A native call holding Python's GIL may delay
the sampler; VmPeak remains a kernel high-water mark. No in-memory sample history
or recording-sized buffer is retained. Snapshot writes are fsynced and the sampler
must join before closure. Original loader exceptions remain original failures.

The failed build05 ASR encoder load is preserved. Its `std::bad_alloc` alone
does not identify physical RAM exhaustion. The retained v28 broker used the same
768 MiB address-space cap with these pre-exec allocator settings:

```text
MALLOC_ARENA_MAX=1
MALLOC_MMAP_THRESHOLD_=131072
MALLOC_TRIM_THRESHOLD_=131072
```

New service and worker execution restores those settings and records their actual
inherited values in `ENVELOPE.json`. AS, CPU, stack and file limits are unchanged.
Fresh native evidence is required to establish whether restoring this policy
resolves the load failure. Logical load success and externally proved process/
cgroup closure remain separate facts.

## Host checks

No environment installation is needed. The fixture driver registers CPU14 before
project imports. It tests synthetic load failure, sampler drainage, output bounds
and observed allocator settings; it runs no native model or SSH command.

PowerShell:

```powershell
$N = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$Q = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/test_native_scope.py" --output-root "$Q/audit-preparation" --checks test_model_memory_failure_keeps_original_error_and_reaps_sampler test_model_memory_capacity_refuses_before_model_call test_frontend_file_hard_limit_allows_finite_worker_derivation
```

Command Prompt or Anaconda Prompt:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%N%\test_native_scope.py" --output-root "%Q%\audit-preparation" --checks test_model_memory_failure_keeps_original_error_and_reaps_sampler test_model_memory_capacity_refuses_before_model_call test_frontend_file_hard_limit_allows_finite_worker_derivation
```

These commands produce fresh owner and `TEST_RESULT.json` receipts. Native
diagnosis uses a new immutable package through the existing reviewed qualification
dispatcher; the helper has no independent native launch command.
