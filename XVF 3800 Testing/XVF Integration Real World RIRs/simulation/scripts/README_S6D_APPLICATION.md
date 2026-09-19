# S6D application evidence helpers

Purpose: `s6d_application_boundary.py` reproduces the exact bound adverse C105/S45_08_07/O0 cached/native pair and changes only one ASR arrival time by ±1ms or to an exact tie around mature evidence. It runs the actual current opt-in scheduler with repair off/on. Original profiles, A15 gallery vectors, telemetry, neural vectors and raw words remain bound; no new model calls, audio playback, firmware, enrollment or hardware access occur.

Inputs: `--output` must name a fresh directory. The helper reads the S6C independent timing review and its exact receipts, evidence, profile/gallery/telemetry/vector hashes. It uses the existing native interpreter and installed NumPy. Original raw inputs are immutable.

Outputs: `RESULT.json` contains original source bindings, own code hash, ten paired replay rows, first-final/latest labels, revision details, gallery query counts, word-invariance assertions and elapsed policy time. Historical 1→21 cp edits/41 words is cited as prior evidence; this helper does not recompute cp or claim an improvement in actual native GUI latency. An adverse result remains in its row. Use a new suffix when repeating; no overwrite.

PowerShell:

```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_boundary.py" --output "$s6dSim\reports\S6D\20260913T195357Z\application\boundary_v3"
```

Anaconda Prompt / Windows CMD (no environment activation needed):

```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_boundary.py" --output "%S6D_SIM%\reports\S6D\20260913T195357Z\application\boundary_v3"
```

For module model-free tests and actual CLI/GUI invocation, read the maintained application README_RESEARCH_S6D.md. Native matrices require separate exact declarations and source snapshots before execution. These model-free replay controls do not provide full-bank focus/direction usefulness scores or CM5 qualification.

## Native pilot planner and single-cell executor

`s6d_application_native.py plan` reads original S6C epoch4 profiles/assets/input bindings and original A15, snapshots current app source, and writes a fresh 12-cell manifest without loading models. The matrix is C065 original/repaired on two scenes, C088 original/delivery-only/repaired on two scenes, and C105 original/repaired on the arrival case. These are source-paced diagnostics, not finalist scope. Input `.wav` sources are read by the application only; there is no audio playback or device open.

`run-one` starts exactly one manifest cell using the frozen source and original weights, explicit single-thread profile, exact gallery and once-gained O0/O0 input. It writes session artifacts, actual-consumer JSONL, 0.25s resource/queue samples with measured sampling gaps, and RESULT.json. It requires fresh cell output and C>=50GiB/G>=75GiB free space. An external owner/supervisor should dispatch serially, preserve failed outputs and enforce the total run/payload budgets. This helper does not create a supervisor or schedule Codex. Use the declared 180s cell limit plus bounded finalization; no destructive restart. It never claims GUI/physical/CM5 testing from CLI success.

Both original and repaired cells receive the same narrow `_emit` instrumentation wrapper, `pilot_publication_monotonic_sec`, so first-text timing shares one clock. It changes no profile or decoder. Source-start and model-ready events separate startup and source pacing. `progress.json` is refreshed at most every 5 seconds and includes job/PID creation identity, admitted and processed source seconds, total duration, phase and queues for an external supervisor. Resource observer exceptions are recorded as failures. The process tree is sampled without a broad filesystem scan.

PowerShell (replace fresh version suffixes if occupied):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_native.py" plan --directory "$s6dSim\reports\S6D\20260913T195357Z\application\native_pilot_v3" --payload 'G:\Just_Peachy_S6D\20260913T195357Z\application\native_pilot_v3'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\reports\S6D\20260913T195357Z\application\native_pilot_v3\helpers\s6d_application_native.py" run-one --manifest "$s6dSim\reports\S6D\20260913T195357Z\application\native_pilot_v3\MANIFEST.json" --job-id 'C065_S45_01_06_original'
```

Anaconda Prompt / CMD, using `%S6D_SIM%` above:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_native.py" plan --directory "%S6D_SIM%\reports\S6D\20260913T195357Z\application\native_pilot_v3" --payload "G:\Just_Peachy_S6D\20260913T195357Z\application\native_pilot_v3"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\reports\S6D\20260913T195357Z\application\native_pilot_v3\helpers\s6d_application_native.py" run-one --manifest "%S6D_SIM%\reports\S6D\20260913T195357Z\application\native_pilot_v3\MANIFEST.json" --job-id "C065_S45_01_06_original"
```

The `run-one` example performs neural inference. A printed PREDECLARED manifest is not an execution receipt. Keep all source snapshots and original S6C controls separate from new results. S6B B36 is not run through this C-generation helper.

V1 and V2 are preserved review drafts and must not be launched. V3 source/manifest still requires root review before execution. The planner now freezes its helper and README beside the application; `run-one` rejects a different helper or previously imported application module from another epoch. Existing model constructors verify all eight asset SHA256 values before initialization; do not repeat large-asset hashing in a heartbeat.

The same-process supervisor API is `run_one(manifest_path, job_id, checkpoint=None)`. The optional callback receives keyword arguments `engine`, `telemetry`, `job`, and `output` before source startup, immediately after `start_file`, and every consumer-loop iteration. A supervisor verifies its own run/PID-bound STOP request, calls `engine.stop()`, and raises an interruption error. This records FAILED even when the engine happens to reach COMPLETED during stopping. Initialization remains synchronous between those checkpoints; the supervisor must distinguish startup and use the declared bound. The function returns the result dictionary only after successful finalization or writes FAILED and raises.

Completion requires drained event consumer, joined finalizer and engine workers, drained and closed policy/punctuation/journal queues with accepted=completed, no retained live-lane lease, and a joined error-free resource observer. RESULT includes `completion_errors`; failures cannot become COMPLETE simply from process exit zero. Failed outputs are preserved for inspection.

`s6d_application_native_checks.py` tests the actual execution loop with a fake model-free engine: stop before startup, stop immediately after startup, complete callback coverage, and rejection of mismatched worker counts. Inputs are temporary owned fixture directories and synthetic events; output is unittest stdout plus temporary result receipts inspected by assertions. It loads no neural model or hardware.

PowerShell:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_native_checks.py"
```
Anaconda Prompt / CMD:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_native_checks.py"
```
