# Joined V3 delivery-cell evidence review

Purpose: review_application_cell_v3.py composes the explicit V3 transport/native/
delivery reader with review_application_observations_v2.py for the new application
variant. Existing V1/V2 cell and original observation readers are immutable.
The observation variant reuses qualified backend/gallery, phase-clock and final
span helpers, and keeps independent engine/archive, resource and viewport checks.
It requires the new cell status and delivery policy in both preparation and result.

Inputs: a stopped cell folder and expectations from an independently reconstructed
V3 production plan, including audio-only job/contract/source/gallery/runtimes,
plan digest, exact coordinator identity and fixed runner/interpreter/code bindings.
Transport must pass before observation work begins. The actual application owner
from verified transport is supplied to the resource reviewer. No source, model,
application, GUI or child process is created by these readers.

The composed reader joins identical evidence bindings across independent passes,
then compares native session terminal files and source-start publication with the
engine, consumer and viewport clocks. V3 adds delivery-envelope reconstruction,
exact planned/engine/trace sample census and a shared delivery/native/consumer/
viewport origin. The last recorded append must precede the engine closure capture.
Scheduling and append costs remain raw; they are never subtracted from latency.
Changing a shared receipt or review result between readers fails the join.

Output is an in-memory PASS_V3_APPLICATION_CELL_EVIDENCE_JOINS_ONLY record with
transport, observation and cross-evidence results, source counts and bindings.
It grants no N4, accuracy, naming, physical paint/scanout, controlled-resource,
deployment-tier, continuity or restart acceptance. Only the terminal lease and
sampled process identities exist; their historical limits remain explicit. This
single-cell API cannot establish its own expected population from available files.
A qualified V3 full-panel reader must reconstruct the exact full plan first.
Content/timing/naming review still needs explicit integration with the new path.

The guarded probe uses 11 regression checks with real readers and fabricated
source/owner/clock/resource/viewport/transport/native/delivery facts. Historical
closed terminal/archive metadata is copied only into fresh fixtures. Binary append
times are synthetic; no audio is opened. Checks cover end-to-end composition,
never-visible spans, source/publication/terminal joins, binding conflicts, resource
owner substitution, early failure, changed display metadata, late append completion
and rejected old observation statuses/policies. No actual run is reviewed.

Private outputs: PROBE_OWNER.json, five source snapshots, ADMISSION.json, tests.txt,
synthetic joined evidence, and RESULT.json or FAILED.json. Keep every attempt and
use a fresh directory. The probe runs CPU14 BelowNormal with one math thread, GPU
off, the existing helper lock, 720-second/8-MiB limits, C50/G75-GiB floors and the
shared 50-GiB allowance including 6-GiB reserve. It verifies exact active D1 owners
and protected source bindings before/after. It is phase-specific: re-observe if
ownership changes, and do not run beside exclusive application measurements.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_cell_review_v3.py" --output "$jpLocal\n4\application-cell-v3-review-probe-v1"
```

Command Prompt or Anaconda Prompt (exact interpreter; no install/activation):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_cell_review_v3.py" --output "%JP_LOCAL%\n4\application-cell-v3-review-probe-v1"
```

Internal API after independent plan/run admission (descriptive variable names):

```python
from review_application_cell_v3 import review_cell
result = review_cell(cell_directory, payload=reconstructed_payload,
    plan_sha256=reconstructed_plan_digest, coordinator=verified_run_owner,
    code=qualified_runner_code, executable=qualified_interpreter_binding,
    coordinator_argv=verified_run_command, state=bound_supervision_directory,
    checkpoint=resource_and_deadline_guard)
```

Do not call this with invented expectations and label the output accepted. A
passing development probe is implementation evidence only. The original checkout,
user input desktop and powered-off Pi remain untouched.
