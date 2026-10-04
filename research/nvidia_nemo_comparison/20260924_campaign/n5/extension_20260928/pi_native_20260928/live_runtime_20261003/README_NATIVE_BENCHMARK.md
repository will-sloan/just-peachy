# Explicit saved-input Nemotron benchmark

`native_benchmark.py` prepares or runs one selected geometry against one pinned
WAV. It uses the exact existing installed adapter and `nemotron_binding.bind`,
the existing Q8 model, and retained delayed LRU1 or streaming/Chunk52 LRU8 native
libraries. It runs no ASR, embedding model or live capture. It does not modify
the installed application, v27, v28, model assets or old source files.

The default action is a host plan. Native execution requires
`--execute-native`, Linux/aarch64, an actual resource unit, a pinned deployment
binding and a fresh private output directory. No SSH operation or native/model
execution was performed while preparing this tool. Passing a host contract does
not qualify a new geometry, identity accuracy or sustained real-time behavior.

## Inputs

- `--input`: existing mono PCM16 16 kHz WAV, with no implicit resampling/gain.
- `--input-sha256`: exact lowercase SHA256 of that matched WAV. Use the same
  approved file and pin when comparing explicitly chosen profiles.
- `--profile`: one ID from `profiles.py`, such as `current_delayed`,
  `official_very_low`, `chunk52` or `candidate_2`. Experimental rows additionally
  require `--experimental`. There is no automatic Cartesian sweep.
- `--output`: a new private directory whose parent already exists. Existing
  output directories are rejected; failed outputs remain available.
- `--duration`: maximum audio policy, 300 seconds by default. An ordinary input
  must fit in full; the tool does not silently take a prefix.
- `--block-samples`: one bounded input block, default 1600 samples / 100 ms.
- `--wall-paced`: simulate source availability against a monotonic 16 kHz
  clock. Without it, source reads run as fast as processing allows.
- `--repeat-seconds 3600 --duration 3600 --developer-soak`: explicitly replay
  the same WAV continuously for one hour of source samples without resetting the
  model. Larger finite durations are allowed by the session policy. Only a block
  is assembled in RAM, even across loop boundaries. This is clearly labeled
  repeated input and is not an hour of newly recorded speech.
- `--drain` and `--backlog`: separate processing and simulated input-backlog
  limits, each defaulting to 120 seconds. Extended drain needs developer policy.
- Native only: `--binding`, `--binding-sha256` and `--unit`. The binding is the
  new runtime's already pinned deployment binding, with installed release,
  manifest and retained profile descriptor paths. This tool validates its pins
  and imports only the standalone adapter, avoiding UI/controller bootstrapping.

Use a fresh native process for every geometry, including when comparing two
profiles on the same input. Model state is persistent across all pushes and
repeated-input boundaries within that process.

For the separate, reviewed thread2 Chunk52 build only, supply the paired
`--native-variant PATH --native-variant-sha256 SHA` arguments. This requires
experimental saved anonymous Chunk52 and the exact isolated build receipts;
normal profile/library pins are unchanged. See
[README_NATIVE_VARIANT](README_NATIVE_VARIANT.md) for admission, commands and
additional provenance outputs. A host plan records the request as unverified.

## Outputs and measurements

The private directory contains early `REGISTERED_OWNER.json`, `PLAN.json`,
native `ENVELOPE.json` when applicable, `MODEL_INIT.json`, `RESULT.json`, and
segmented binary files:

- `probabilities-f32le-*.bin`: all new eight-column float32 probability rows in
  little-endian row-major order. Concatenate parts in manifest order. The result
  has byte counts and SHA256s for every part and the complete byte stream. Parts
  are at most 16 MiB; total bytes are reserved from the exact output-frame bound.
- `calls-jsonl-*.bin`: UTF-8 JSON lines containing initialization-independent
  push/finish timings, absolute input sample counters, source/repetition
  provenance, exact frame intervals, rolling push RTF, backlog and resource
  samples. These parts may split a JSON line at a part boundary; concatenate
  them before parsing. The next build reserves at most 8192 bytes per call,
  including bounded task affinities; the frozen build01 reserved 4096.

Model initialization is timed separately and includes the adapter's existing
asset verification. Every push and finish reports dispatch wall time, process
CPU time and the adapter's compute duration. Rolling RTF is push-only;
`component_rtf` includes push plus final flush against actual delivered audio.
Benchmark artifact writes, input hashing and model initialization are outside
that component RTF. Source-phase wall time also includes pacing and benchmark
bookkeeping, so it is a different measurement.

In wall-paced mode, input backlog is simulated source-clock availability minus
submitted samples. Speaker backlog additionally includes frames not yet emitted.
Neither metric is physical microphone latency. RSS, peak RSS, process CPU time,
CPU utilization between calls, available memory and sysfs thermal zones are
recorded where available; unavailable fields remain null. No 4 GB or 8 GB result
is inferred from a 2 GB run. The next-build sampler also records `virtual_bytes`
(`VmSize`), `peak_virtual_bytes` (`VmPeak`), `swap_bytes` (`VmSwap`) and `pss_bytes`
from Linux procfs. PSS reads use `smaps_rollup` at most once per second per process;
`pss_sample_age_seconds` makes cached observations explicit. Other process
fields are sampled per call. `memory_scope=benchmark_process` excludes separate
processes; available RAM is system-wide. The frozen build01 sampler is unchanged.

The next build also samples `/proc/self/task` at most once per second, recording
task count, at most 64 actual task affinity masks, cache age and truncation status.
A truncated count is a lower bound of 65. These boundary samples can miss short
lived graph workers; task count is not a measurement of concurrently busy threads.
`ENVELOPE.json` records `thread_environment=1` and the four exact environment
values, while `native_graph_threads=unverified` avoids an unsupported inference
from those variables. Earlier frozen `model_threads=1` metadata is not proof of
the native graph's thread count. See [the source audit](README_NATIVE_OPTIMIZATION.md).

An allocation failure near the imposed 768 MiB address-space bound with plenty
of available RAM is evidence to investigate that hard limit, not proof that 2 GB
physical RAM is exhausted. Falling available memory, PSS/RSS growth or swapping
support a physical-pressure investigation. Stable memory with increasing backlog
and high compute cost points toward CPU throughput. These are diagnostic patterns,
not automatic causal classifications; preserve the actual failure and limits.
Additional 4/8 GB capacity cannot remove an unchanged `RLIMIT_AS` or increase the
admitted CPU quota.

The final receipt checks the exact sample count and source-derived native EOF
rule: nonempty input has `samples // 160 + 1` output rows on the 10 ms output
clock. It verifies input bytes and file identity again, records actual model
closure/pointer status, and labels errors `FAILED_PREFIX_PRESERVED`. Invalid or
nonfinite probabilities are not exported as valid rows. A completed component
run still sets `quality_evaluated=false` and `sustained_realtime_qualified=false`.

## Host plan: PowerShell

Set the input path and known pin to the chosen retained WAV. This example first
registers CPU14 ownership before reading project code, then lets the CLI create
its own fresh child output receipt. The existing Anaconda interpreter needs only
its already installed `psutil`; plan mode does not import NumPy or model code.

```powershell
$env:JP_BENCH_CODE = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/native_benchmark.py'
$env:JP_BENCH_PRIVATE = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$env:JP_MATCHED_WAV = 'REPLACE_WITH_EXISTING_MATCHED_WAV_PATH'
$env:JP_MATCHED_SHA256 = 'REPLACE_WITH_EXACT_LOWERCASE_SHA256'
$code = @'
import psutil
psutil.Process().cpu_affinity([14])
import json, os, sys, uuid, runpy
from pathlib import Path
out = Path(os.environ['JP_BENCH_PRIVATE']) / ('presets-preparation-benchmark-cli-' + uuid.uuid4().hex)
out.mkdir()
me = psutil.Process()
with (out/'REGISTERED_OWNER.json').open('x') as f:
    json.dump(dict(pid=me.pid, create_time=me.create_time(), affinity=me.cpu_affinity()), f)
    f.flush(); os.fsync(f.fileno())
sys.path.insert(0, str(Path(os.environ['JP_BENCH_CODE']).parent))
sys.argv = ['native_benchmark.py', '--input', os.environ['JP_MATCHED_WAV'],
    '--input-sha256', os.environ['JP_MATCHED_SHA256'], '--profile', 'official_very_low',
    '--experimental', '--output', str(out/'plan')]
runpy.run_path(os.environ['JP_BENCH_CODE'], run_name='__main__')
'@
& 'C:/Users/amiri/anaconda3/python.exe' -B -c $code
```

For the explicit hour plan, add the following arguments to `sys.argv`:

```python
'--duration', '3600', '--developer-soak', '--repeat-seconds', '3600', '--drain', '600'
```

## Host plan: Command Prompt or Anaconda Prompt

Replace the two matched-input values first. Use the same known WAV/pin as in the
PowerShell example. These commands perform a plan only.

```bat
set "JP_BENCH_CODE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/native_benchmark.py"
set "JP_BENCH_PRIVATE=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
set "JP_MATCHED_WAV=REPLACE_WITH_EXISTING_MATCHED_WAV_PATH"
set "JP_MATCHED_SHA256=REPLACE_WITH_EXACT_LOWERCASE_SHA256"
"C:\Users\amiri\anaconda3\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import os,json,sys,uuid,runpy; from pathlib import Path; o=Path(os.environ['JP_BENCH_PRIVATE'])/('presets-preparation-benchmark-cli-'+uuid.uuid4().hex); o.mkdir(); p=psutil.Process(); f=(o/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); sys.path.insert(0,str(Path(os.environ['JP_BENCH_CODE']).parent)); sys.argv=['native_benchmark.py','--input',os.environ['JP_MATCHED_WAV'],'--input-sha256',os.environ['JP_MATCHED_SHA256'],'--profile','official_very_low','--experimental','--output',str(o/'plan')]; runpy.run_path(os.environ['JP_BENCH_CODE'],run_name='__main__')"
```

## Native command, for an already admitted CM5 unit

The operator must first reserve the input/assets/output and create the actual
user service/scope with `AllowedCPUs=2,3`, `CPUQuota=200%`, `TasksMax=64`, a finite
external wall deadline covering the plan, and the four numerical-library environment
values equal to one. The process must actually belong to the supplied unit.
The CLI checks those CPU/task properties, requires at least 850 MiB available
RAM initially, and reserves maximum output bytes above a 5 GiB free-disk floor.
It sets 768 MiB address-space, 1 MiB stack, 32 MiB per-file and finite CPU-time
limits, checks the 192 MiB runtime free-memory floor and finite total deadline at
dispatch boundaries. The external unit deadline handles a stuck native call;
an unfinished receipt is not a successful closure.

Within that admitted unit, replace the uppercase path/pin/unit placeholders:

```sh
python3 -B N/native_benchmark.py \
  --execute-native --unit UNIT.service \
  --binding BINDING.json --binding-sha256 BINDING_SHA256 \
  --input MATCHED.wav --input-sha256 MATCHED_WAV_SHA256 \
  --profile official_very_low --experimental \
  --output FRESH_PRIVATE_OUTPUT --wall-paced
```

For one explicit continuously repeated hour, additionally use:

```sh
  --duration 3600 --developer-soak --repeat-seconds 3600 --drain 600
```

Remove `--wall-paced` to measure unpaced throughput on the same sample stream.
That run measures one hour of repeated source audio, not necessarily one hour of
wall time. Never label it a real-time soak. Do not start multiple geometries in
parallel or treat this example as permission to contact/start the Pi.

## Host contract tests and API

Use the CPU14/early-registration test commands in
[README_PIPELINES](README_PIPELINES.md#run-the-focused-tests), replacing
`test_pipelines` with `test_native_benchmark`. NumPy is used only to create fake
model outputs. Set `JP_BENCH_TEST_ROOT` to the private preparation directory if
temporary fixture files should be contained there. The tests remove their own
temporary fixtures after verification.

The original six tests passed, zero failures/errors, in
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-benchmark-tests-7dc05fb5a99c4db1860b85ee46dfada0/RESULT.json`.
They cover matched-input pins, no implicit truncation, a bounded continuous
hour-replay plan, exact segmented hashes, full sample/frame/EOF accounting,
model init/push/finish timing records and failure-prefix preservation. No model
or native library ran.

Additional focused contracts cover Linux virtual/swap/PSS fields, 1 Hz PSS and
task-affinity caches, bounded task scans and the explicit unverified graph-thread
status. They use synthetic procfs observations and do not run native code.

Programmatic contracts are `inspect_wav(path, sha256)`,
`make_plan(info, selection, policy, repeat_seconds=None, wall_paced=False)`,
`load_factory(binding_path, binding_sha256, selection, policy, session_id)`, and
`run_stream(plan, factory, numpy, output, native_execution=True, guard=guard)`.
Only the guarded native CLI should claim actual native execution; dependency-
injected host tests pass `native_execution=False` and generate no qualification.
