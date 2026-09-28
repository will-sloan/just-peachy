# Causal saved-source clock foundation

Purpose: implement the common release-clock foundation for catalogue P01-P06
before connecting it to real application workers. Supports unpaced, 1x,
half/double-rate, fixed jitter and burst delivery. It keeps every source sample
and the exact final remainder. It does not implement a diarizer, gate, GUI or
worker topology. Those integrations still need separate implementation/evidence.

Inputs: total saved-source frames, sample rate, chunk size, mode and speed.
`schedule` produces immutable source intervals with deadlines. `deliver`
accepts an iterator and a bounded-enqueue callback, waiting against one absolute
monotonic clock and passing actual availability to the consumer. A slow callback
adds visible lateness without resetting the source clock. A real integration
must provide saved PCM for the exact intervals and log downstream availability.
Missing frames or regressing deadlines/clocks are errors. Cancellation leaves
unpublished work unclaimed. No microphone, playback, model or device API exists
in this module.

Jitter repeats 0/20/80/200ms added delay and preserves ordering. Burst mode
waits for each two-second source boundary before releasing buffered chunks;
the last partial burst also waits for its boundary. It does not synthesize
new speech, compress silence or alter source timestamps. Speeds other than 1x
are explicitly diagnostic. Long sessions must declare their saved-source joins.

Output of the CLI: a fresh JSON plan with source intervals and **planned**
deadlines. The CLI does not run the delivery loop or claim measured latency.
It reads no WAV. Use private campaign output paths and preserve existing plans.
Input/source/model bindings and admission belong to the eventual application
adapter, not this planning-only CLI.

Eight unit tests cover exact remainder, causal jitter/bursts, slow consumers,
early timer wakeups, cancellation, invalid source accounting and speed labels.
They use an injected clock, so these are deterministic clock-contract tests,
not evidence that Windows/CM5 real-time scheduling or model throughput passes.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\realtime_validation_v1
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B -m unittest test_source_clock_v1 -v
& $jpPy -B source_clock_v1.py --frames 715127 --mode jitter --output G:\Just_Peachy_N1\20260924_campaign\local\n5\realtime-clock-v1\jitter-plan.json
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\realtime_validation_v1
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_source_clock_v1 -v
"%JP_PY%" -B source_clock_v1.py --frames 715127 --mode jitter --output G:\Just_Peachy_N1\20260924_campaign\local\n5\realtime-clock-v1\jitter-plan.json
```

Use `--mode paced --speed 0.5`, `--speed 1`, `--speed 2`, `--mode burst` or
`--mode unpaced` with fresh destinations for other plans. The optional library
callback is for a later admitted application adapter; no new worker is started
by these commands. Current two-CPU/GPU-off admission and fixed campaign limits
still apply. All original 34 catalogue entries retain their historical status.
