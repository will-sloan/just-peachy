# Joined application observation review

`review_application_observations.py` joins the independently qualified source,
worker/consumer/archive closure, viewport replay and resource replay checks for
one stopped application cell. It reconstructs the prepared backend, gallery and
frontend declarations; checks the source/terminal clocks, engine type, final
Controller mode/backend/epoch and CPU-only environment; joins resource phases
and viewport observations to the same source origin; and compares final
Controller span metadata with the latest observed viewport rows.

Never-visible captions and finalized captions with no observed final visibility
remain explicit counts. A successful structural join does not mean those
captions became visible, correct or timely. Actual pane strings, names, native
publication contents, reference metrics and continuous exposure are not scored
here. Phase intervals are reported without subtracting pacing error. Target
memory tiers, physical scanout, restart and continuity remain unqualified.

Inputs are the private closed `application` directory, exact audio-only payload
from a reconstructed production plan, and expected process PID/creation
identity. Outputs are a private dictionary with rechecked evidence bindings,
component review results, phase intervals and final-span counts. Status is
`PASS_APPLICATION_OBSERVATION_JOINS_ONLY`; all integrated acceptance remains
zero. Records use the bounded transport reader; viewport/resource logs retain
their existing independent bounds. Source session files must remain under the
cell's data/sessions and archive metadata under its data/conversations.

The internal `review_collected_cell(folder, checkpoint=..., **expected)` first
calls the qualified transport review, then this observation review with the
exact application owner. It returns `PASS_APPLICATION_CELL_EVIDENCE_JOINS_ONLY`.
The caller must still independently reconstruct the complete qualified panel
plan and terminal population, review native publication/content and score
naming/accuracy/timing. These APIs do not create a production admission. There
is no standalone command for passing arbitrary expectations as acceptance.

The historical native finalization/archive metadata used by the tests is copied
into private fixture directories. All new owner, clock, Controller, viewport and
resource observations in those tests are explicitly synthetic. Tests invoke
the real independent validators, with no model, saved-audio replay, Tk window,
microphone, playback or private desktop creation. This proves composition and
failure detection only, not an actual successful N4 application run.

`probe_application_observation_review.py` runs 12 tests with current D1 ownership
checks, CPU14 placement, the existing helper lock, 720-second limit, disk floors
and shared payload reserve. It binds the current qualified dependency versions,
preserves the new source files, and writes private ADMISSION.json, tests.txt,
synthetic fixtures and RESULT.json (or FAILED.json). The numerical owner stays
on CPU4. The probe is phase-specific to active D1; use a versioned admission
update if the campaign has advanced. Use a fresh output on every attempt.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_observation_review.py" --output "$jpLocal\n4\application-observation-review-probe-v2"
```

Command Prompt and Anaconda Prompt (the exact interpreter requires no activation
or installation):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_observation_review.py" --output "%JP_LOCAL%\n4\application-observation-review-probe-v2"
```

V1 is preserved with its source snapshots and failed fixture log. It exposed
the distinction between stored catalog `manifest_id` and the runtime catalog's
derived `id` alias. The repaired reviewer uses the stored manifest identifier
and verifies its composition hash. V2 is the fresh output in the commands above.

Successful development qualification is
`PASS_APPLICATION_OBSERVATION_REVIEW_CHECKS_ONLY`. Its public receipt binds the
tested source and private results. Keep all fixture metadata and application
transcripts private; only the small redacted qualification belongs in Git.
Actual full production panels, content scoring and continuity remain pending.
