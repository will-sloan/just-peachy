# Saved-source delivery observer

Purpose: `source_delivery.py` records when the existing FileSource's unchanged
20-ms absolute schedule reaches its input MemoryJournal. It measures append
entry and return against `source_origin + end_sample / 16000`. This is saved-file
source delivery, not a microphone callback or physical audio latency measurement.
The existing journal archival observer is preserved. No audio, gain, pacer,
predictor, UI, source-stop policy or existing qualified runner is changed.

Inputs to the utility: one freshly constructed actual FileSource, its fresh
16-kHz MemoryJournal, and the admitted eight-field audio-only job. The enclosing
application runner must verify the audio hash, source inventory, application
admission and exclusive resource slot before construction. This utility cannot
admit a run. Install before FileSource.start, after its real input journal has
been assigned. Nonzero starting cursors, restarted sources, existing append
instrumentation and files longer than one hour are refused. Each new session
requires a new source and observer. Private test seams are explicitly stamped.

Observation: instance-level source status and journal append hooks forward the
original callback/block exactly once and preserve original exceptions. Numeric
records accumulate in a bounded bytearray. No waveform copies or disk writes
occur in the observer's source path. Each record is 29 little-endian bytes:
start sample, count, committed count (three uint32), append entry/return
perf_counter seconds (two float64), and raised flag (uint8). At one hour this is
180,000 records / 5,220,000 bytes. A partial last chunk is retained exactly.
The existing archive observer's work is included in append-call duration.
Instrumentation overhead exists and is never subtracted or represented as zero.

Original-source failures, wrong producers, duplicate/invalid starts, changed
hooks, missing/out-of-order chunks, counter disagreement, capacity exhaustion
and invalid clocks make the observation unusable. They do not silently suppress
or replace the original source operation. A valid observed prefix is retained.
Close only after the source thread exits; the observer does not stop or join it.
Only its own hooks are restored, and foreign replacements are preserved and
reported. Calling close twice fails. A partial stop is explicit and cannot count
as full delivery; this alone is not a functional Controller restart test.

Outputs: `SourceDelivery.close()` returns a metadata dict and binary trace.
The future admitted application variant must write both to its private cell
directory after source closure, bind them in its receipt, and independently
review the whole trace with `summarize`. It must also join source origin/counts
to the already recorded consumer-source clock and actual engine closure. There
is deliberately no standalone production replay CLI. Existing immutable V2
runner/child/planner/reviewer bindings do not yet include this observer. A new
explicit variant, integration qualification and actual controlled runs remain.

The independent parser retains signed early/late times and nearest-rank p50,
p95, p99, min/max, raw counts beyond 5/20 ms, append duration and entry gaps.
These thresholds are diagnostics, not an acceptance test. Zero observations
have null quantiles. No GUI timing is corrected using these measurements, and
no device callback, word boundary, UI paint, resource tier, continuity or N4
acceptance follows from a successful observer development probe.

`probe_source_delivery.py` verifies fresh D1 exact ownership/heartbeat/bindings,
disk reserves, the private inventory allowance and CPU14 model-free helper lock.
It snapshots the four new files, runs 18 checks with a 12-minute / 8-MiB output
limit, and rechecks ownership and bound code. The unchanged FileSource,
MemoryJournal and AbsolutePacer class bodies are AST-extracted from the exact
qualified source files. Fake soundfile/thread/time interfaces use RAM-only
numeric fixtures; no WAV, app/model graph, GUI, device or Pi is opened. A single
real helper thread tests wrong-producer rejection and is joined. This is not
production threading, source-speed, full-application or actual continuity proof.

Checks compare instrumented and uninstrumented source outputs, callbacks,
schedule and archive hooks; check the partial final chunk, partial stop and
fresh observer isolation; preserve exact original exception objects; reject
tampered traces and foreign hooks; retain forwarding on observer failure;
check early/late signed metrics and the one-hour binary budget. Integration and
future resource comparison must use identical observation policy across paired
candidates and account for the observer's own memory/CPU cost.

PowerShell development probe (use a fresh output suffix for every attempt):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_source_delivery.py" --output "$jpLocal\n4\source-delivery-probe-v1"
```

Command Prompt and Anaconda Prompt (direct pinned interpreter, no environment
activation or installation required):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_source_delivery.py" --output "%JP_LOCAL%\n4\source-delivery-probe-v1"
```

Private probe outputs: PROBE_OWNER.json, source snapshots, ADMISSION.json,
tests.txt, SYNTHETIC_DELIVERY.json/.bin, TRACE_BUDGET.json and RESULT.json or
FAILED.json. The maximum-size binary is sized/parsed in RAM and is not saved.
Only code, documentation and redacted hash/qualification metadata belong in
Git. Actual source paths, timings, source traces and campaign evidence stay
private. A failed attempt is preserved; fix code only in an unqualified working
version and choose a fresh attempt directory.
