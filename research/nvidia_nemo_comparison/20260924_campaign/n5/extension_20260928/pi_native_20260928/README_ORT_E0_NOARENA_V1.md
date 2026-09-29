# Native ReDimNet CPU arena comparison

Purpose: determine whether disabling ONNX Runtime's CPU arena reduces retained virtual/RSS allocations without changing the existing embedding output. This isolated derivative changes only `SessionOptions.enable_cpu_mem_arena=False`, adds per-case `/proc/self/status` memory snapshots and compares each normalized vector to the preserved arena-enabled reference. Memory-pattern and graph optimizations remain unchanged. No model conversion, training, enrollment, capture or accuracy scoring.

Inputs: installed hash-bound ReDimNet model, original saved PCM prefixes of 0.5/2/12 seconds, six vectors and independent REVIEW from `ort-e0-lifecycle-v2`, and a fresh host/target census. Output: private admission/owner, six arrays, timing/memory snapshots, RESULT and separately written REVIEW. All vectors remain private. Per-stage snapshots can miss transient peaks; overall peak RSS is recorded separately. Original rc5 app stays active, making costs conditional.

The predeclared gate is finite normalized 192-dimensional vectors, unchanged input, all six maximum absolute differences <=1e-5 to the arena-enabled reference, repeat parity, session release and natural process/owner closure. Passing does not establish identity accuracy, integrated B01 fit or long-run stability. A failure is preserved. Disabling an allocator is not by itself evidence of memory savings.

## PowerShell

From this directory, after validating the fresh census:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_ort_e0_noarena_v1.py --run-id ort-e0-noarena-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V12.json'
```

## CMD / Anaconda Prompt

Use `cd /d` to this directory, invoke the same quoted Python executable and arguments without `&`. No environment installation/download is required. Dispatcher uses strict SSH stdin and the installed Pi Python; existing outputs are refused. Preserve failed attempts and immutable parent sources.

Limits remain CPUs2/3,totalCPU200%,one native thread,Tasks64,180seconds,hard768MiB RLIMIT_AS,>=850MiB available RAM and5GiB disk,16MiB fresh-output reservation within the combined1GiB window. Telemetry is disabled before initialization only for this process; glibc arena1 remains as in the parent. No higher cap or OS/swap change. Independently rehash admitted assets/output arrays, recompute the same gates and verify exact boot/PID/start ticks closure before crediting the run.

The official [Python API](https://onnxruntime.ai/docs/api/python/api_summary) documents `enable_cpu_mem_arena`; [runtime source](https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/core/framework/session_options.h) explains its preallocation policy (checked September29). This experiment measures this installed runtime rather than inferring a benefit from the option.
