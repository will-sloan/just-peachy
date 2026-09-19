# S6B matched paced full-engine probes

`s6b_paced.py` prepares and runs a bounded native CPU study against an immutable
execution epoch. It does not modify APP or the campaign's runner/scoring code.
Preparation and `--mode check` are model-free. Do not launch the paced study
until the owning coordinator reserves one model-worker slot; the driver rejects
a launch when four frozen-epoch workers are still alive.

## Purpose and scope

The eventual profile set is historical B00, the selected best voice family and
two distinct joint finalists. The owner supplies the finalist IDs after the
challenge screen. No finalist is selected by this driver, and no repetition is
discarded because its labels or score are worse.

Default metadata-fixed cases are:

| Case | Condition |
|---|---|
| S45_01_06 | Isolated single-participant speech |
| S45_03_01 | Complete short replies and rapid handoffs, including subsecond speech |
| S45_04_05 | Two-talker scheduled overlap |
| S45_06_07 | Silent relocation and long-paused return |

The final planned study explicitly uses both taps with `--streams O0,O1`.
The exact prepared files have44.6954375seconds each. Four profiles x four cases
x two repetitions x two taps is64jobs and47.68minutes of paced audio, plus loading
and finalization. No prefix trimming, concatenation, re-rendering or new gain is
performed. The nominal rendered scene duration45seconds is kept distinct from
the actual indexed recording. The CLI's historical default remains O0, so the
final-study command must supply the two-tap argument explicitly.

Each cell runs a fresh process and empty enrollment gallery. Candidate cells
load `ResidentModelBundle` and execute the normal resident models for the entire
scene with fresh stream/tracker/scheduler/endpoint state. Cold admission/loading
is measured separately. This probe does not measure cross-scene warm-cache
throughput; the main campaign already exercises that reuse. B00 imports the
exact immutable S6A `baseline_app` with original configuration and explicit
unchanged model assets. Its model-thread defaults are preserved rather than
silently normalized to candidate settings. All numeric-library environment
pools are1before native imports; that is not an OS thread-count cap.
Preparation verifies every B00 Python module against the historical S6A
execution contract, including the exact module inventory. Preparation and worker
admission reject Python/NumPy/ORT/Sherpa versions different from frozen epoch2.
The second repetition reverses method order to reduce fixed order bias; this
small probe does not eliminate changing host contention or thermal history.

## Inputs and outputs

Inputs are the frozen `EPOCH2_EXECUTION_MANIFEST.json`, its bound effective
profile registry, input/gain indices, fixed assets, immutable APP code, and
sanitized telemetry where the selected profile enables cues. The preparation
step reads scene metadata only to document condition coverage; references and
participant data are never passed into application predictor APIs.

The output directory must be a dedicated new G: namespace. It contains:

- MANIFEST.json and PREPARATION.json with exact code/profile/input/asset bindings.
- Per-cell launch, PID creation, native session and immutable COMPLETE receipts.
- PROCESS_SAMPLES.jsonl at approximately0.5second cadence for every accessible
  member of the owned process tree, and LIVE.json at approximately0.25seconds.
- Current-run native event times, stable IDs, first/latest labels and revision
  visibility in DISPLAY_EVENTS.json; original event logs remain intact.
- SUMMARY.json with every cell, paired repetition comparisons and missing jobs.
  A compact copy is placed under REPORT/paced/<output-name>/SUMMARY.json.

Memory fields distinguish private resident USS, RSS-sum upper bounds, Windows
private commit and a nonunique RSS-minus-USS shared-resident estimate. PSS is null
when unavailable. Inaccessible process-tree members are marked and do not become
zero-memory claims. CPU/write counters include the worker's observation/export
overhead; the coordinator is separately sampled. Startup, observed OS threads,
ASR/speaker backlog trajectories and log/journal growth are retained. No Ryzen
to CM5 multiplier,2GB fit assertion, GUI latency or thermal qualification is made.
First/last process and paced USS/RSS/private-commit values are reported. These
one-recipe fresh-process trajectories are distinct from a campaign worker that
has switched recipes; allocator retention is possible and a delta alone does
not establish a leak.
Both taps provide16 whole-scene cells per profile across conditions and
repetitions. These are repeated fresh-process trajectories, not one uninterrupted
12-minute resident-model run; no longer continuous stability test is implied.

Complete PCM bytes/hash, source duration, ASR cursor and durable completion are
checked for every method. Candidate internal dispatch spans additionally prove
no gaps/duplicate samples and include the exact EOF tail. Historical B00 lacks
those extra internal dispatch records; its journal/cursor/finalization checks
must not be described as an instrumented per-accept trace.
R6 prepared sources use FLOAT WAV encoding. Expected journal bytes are computed
with float32 SoundFile decoding, float32 mono averaging and the frozen
AudioJournal's exact round/clip PCM16 conversion, with no gain reapplied. The
model-free check exercises both PCM16 and FLOAT inputs through the actual frozen
WavSource/AudioJournal, including a107sample EOF tail.

`native_emission_minus_source_cursor_sec` uses the current run's source-start
and event UTC stamps. It includes source pacing, dispatch and conservative
scheduler release, and can be affected by a host wall-clock adjustment. Modeled
cue/evidence availability is retained separately; it is not measured display
latency. Speaker-model vectors/spans, ASR words and native label sequences are
compared separately across repetitions, where the original implementation emits
the required data.

## PowerShell: model-free checks and preparation

The following prepares B00 and B26 as an interface/resource and gain-conversion check. It does not
start neural models and does not represent the eventual four-profile study.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_paced.py' --mode check --report 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_paced.py' --mode prepare --epoch epoch2 --profiles B00,B26 --repetitions 2 --streams O0 --report 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z' --output 'G:\Just_Peachy_S6B\20260909T230840Z\paced_preparation_v4'
```

For the actual study, use a NEW output namespace, replace `B00,B26` with the exact
comma-separated four-profile list supplied by the owner, prepare it, then use
the identical command with `--mode run`. For example, once the chosen list is
stored in `$pacedProfiles`, the preparation/run arguments must use
`--profiles $pacedProfiles --repetitions 2 --streams O0,O1 --output 'G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v1'`.
The finalized exact command will be recorded in REPORT/paced/METHODOLOGY.md when
the IDs are selected. The existing output manifest rejects a changed selection.
In PowerShell and CMD, pass `O0,O1` as the single comma-separated streams value,
without a space after the comma. Do not start until the owner supplies the four
IDs and reserves the model worker after full-bank inference.

## Anaconda Prompt / Windows Command Prompt

Use the explicit EDGE interpreter, which matches epoch2 Python3.11/NumPy2.2.6.
The base Anaconda interpreter is not interchangeable with this frozen runtime.

```bat
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_paced.py" --mode check --report "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_paced.py" --mode prepare --epoch epoch2 --profiles B00,B26 --repetitions 2 --streams O0 --report "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z" --output "G:\Just_Peachy_S6B\20260909T230840Z\paced_preparation_v4"
```

## Stop, resume and failure policy

Create an empty `STOP_REQUEST` in the paced output directory to stop after the
active scene finalizes. The shared REPORT/STOP_REQUEST is also honored at scene
boundaries. Remove only your intended stop marker before running the identical
command again; exact complete receipts are rehashed/reused. `STOP_NOW` in the
paced output stops only owned worker processes and retains a failed attempt.
Ownership is checked with both PID and creation time. Unrelated processes are
never terminated.

Incomplete/failed attempts are preserved and block automatic overwrite. Inspect
the exact failure, fix only an allowed external fault or create a separately
bound corrected run, and retain earlier evidence. Nothing retries because of
poor recognition or attribution. Source files remain frozen throughout a run.
Every new invocation rehashes declared dependencies before model launch; this
does not protect against somebody violating the no-concurrent-mutation rule
after admission. The driver enforces RAM/disk reserves and output cap from the
frozen epoch and emits20second atomic heartbeats during long work.

V1/V2 preparations remain historical and started no neural models. V2's direct
PCM16-body helper did not support FLOAT gain sources; its B00-only preparation
was valid, but it must not be used for R6. V3/V4 validate frozen source conversion,
historical B00 modules and runtime versions, accounts for generic epoch-worker
PID trees and the combined G payload/C report/staging cap. The V3/V4 preparation
also includes B26 solely to exercise FLOAT gain admission, not to select a
finalist. Preparation and ten local checks start no neural models.
