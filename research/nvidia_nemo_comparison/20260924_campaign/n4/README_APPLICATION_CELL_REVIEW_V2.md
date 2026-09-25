# Joined V2 application evidence review

Purpose: `review_application_cell_v2.py` composes the qualified V2 transport and
complete-native-envelope reader with the existing source/worker/archive,
resource and viewport readers. It keeps all earlier code and qualifications
unchanged. It checks that independently valid evidence belongs to one cell,
without promoting collection into integrated acceptance.

Inputs: a stopped V2 cell directory and independently reconstructed production
plan expectations (audio-only payload, plan digest, exact coordinator identity,
runner code/interpreter, command and supervision directory). Transport checks
run first and determine the application identity used by the resource reviewer.
Failure stops subsequent stages. The shared RESULT/ENGINE_CLOSURE bindings must
agree between readers and remain unchanged. Native and engine terminal receipts,
publication/consumption/coalescing counts, source-start serial/time and native,
consumer and viewport source origins must agree. Engine closure capture must
follow the recorded native completion publication. These timestamps use the
same application's perf_counter; process-lifetime clocks are not subtracted.

Output: an in-memory `PASS_V2_APPLICATION_CELL_EVIDENCE_JOINS_ONLY` record with
both independent reviews and joined bindings/counts. Missing or offscreen final
spans remain denominators. This is not a complete production-panel review or
semantic/accuracy evaluation. Raw native text, caption strings, names, latency,
controlled whole-stack resources, physical scanout, continuity, stop/restart and
deployment tiers retain explicit unqualified/UNKNOWN values. Accepted integrated
N4 cells remain zero. Raw transcripts/profiles and all private evidence stay local.

The guarded probe runs only on CPU14 with the existing helper lock and no model,
source or application launch. It verifies D1's current exact owner, heartbeat and
protected code before and after; checks the campaign's disk, allowance and time
limits; and preserves source snapshots, ADMISSION.json, tests.txt and RESULT.json
or FAILED.json. Eight tests run the actual readers on unified synthetic facts.
Copied historical terminal/archive metadata is modified only inside these
explicit fixtures; it is not presented as a newly executed application. Tests
cover full composition, invisible-span denominators, mismatched starts/origins,
late native completion, changed shared bindings, authoritative resource owner
and propagation of transport/observation failures. Inert fixture executables and
scripts are never run. There is no microphone/device enumeration, playback,
training, visible GUI, input/focus control or Pi access.

Use a fresh output for every attempt. Do not run development probes during
controlled application measurements. The full production plan gate and actual
saved-audio application execution remain separate work.

Attempt v1 failed before admission/tests because one public prerequisite stores
its admission binding through the private result. The four exact source files
and failure receipt are preserved; its exited helper identity was not recorded.
The corrected probe resolves that binding through the private result and writes
PROBE_OWNER.json before prerequisite reconstruction. Attempt v2 then exposed a
synthetic lifetime fixture missing its required member-observation event. Its
admission, source snapshots, test log and failed receipt are preserved. That
fixture was corrected without changing production checks. Use fresh attempt v3.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_cell_review_v2.py" --output "$jpLocal\n4\application-cell-v2-review-probe-v3"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_cell_review_v2.py" --output "%JP_LOCAL%\n4\application-cell-v2-review-probe-v3"
```

Internal API for a future qualified full-panel reviewer:

```python
from review_application_cell_v2 import review_cell
checked = review_cell(cell_directory, payload=reconstructed_payload,
    plan_sha256=reconstructed_plan_digest, coordinator=bound_run_owner,
    code=qualified_runner_code, executable=qualified_interpreter_binding,
    coordinator_argv=bound_run_command, state=bound_supervision_directory,
    checkpoint=bounded_evaluator_guard)
```

Those names represent verified inputs, not runnable placeholder values. A caller
must reconstruct the full declared population from the qualified V2 plan; it must
not infer expected cells from the evidence found on disk. Preserve earlier
versions and use a fresh qualified derivative for repairs.
