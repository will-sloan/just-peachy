# Recorded caption-row timing interpretation

Purpose: `review_application_timing.py` composes the qualified application
content reader with a second native-caption read and verifies matching review
fingerprints, source origins and file bindings. It preserves each lexical word's
immutable source uncertainty window, first native display publication and first
native final publication. Empty-caption virtual IDs are counted separately.

Inputs: a stopped V2 cell directory and independently reconstructed panel/run
expectations (`payload`, `plan_sha256`, `coordinator`, child `code`, `executable`,
`coordinator_argv`, `state`), plus a bounded evaluator checkpoint. The production
API derives clocks, roster/settings and native/viewport evidence from that cell;
it accepts no replacement origin or display roster. The internal `project` and
`sampled_state` arithmetic seams do not themselves admit an application run.

Output: a private in-memory `PASS_V2_APPLICATION_RECORDED_ROW_TIMING_ONLY`
review containing the content review, evidence bindings, native span population
and first row-visible, first final row-visible and latest row-observation facts.
For each sampled state it reports:

- Recorded observation time minus the first native publication containing the
  span, and (for the first final-visible row only) its first final publication.
- The range of elapsed times from all compatible preceding native publications,
  with candidate count, ambiguity and fingerprint retained. This does not identify
  the exact consumed event, even when one compatible predecessor remains.
- The signed interval `[observed - source_origin - source_end,
  observed - source_origin - source_start]`. It is revision-window uncertainty,
  not phonetic word alignment or a bound on physical or display latency.
  Negative values are preserved; no pacing error is subtracted.

The viewport collector proves visible caption glyphs at **row** level. Every
span belonging to that row inherits the same visibility flag; clipping can leave
an individual word offscreen. This reader therefore labels the facts as row
observations and never claims individual word-glyph visibility. First-observed
is not exact first paint. Native state first-seen is not widget visibility.
An invisible/retired latest observation remains present. Unobserved, never
row-visible and never final row-visible spans keep their denominators and null
stages. Empty captions do not increase word counts or gain lexical timestamps.
Missing raw caption revisions and partial-only utterances remain explicit.

Maximum sample interval is a diagnostic, not continuous exposure measurement.
No source-callback deadline review, exact latency, naming accuracy, resource tier,
full panel coverage, continuity, stop/restart or N4 acceptance is established.
The current closure data does not persist a per-callback pacing timeline and
the viewport data does not persist per-word glyph visibility. Those claims need
separately designed, bounded instrumentation and actual source-paced retests;
this arithmetic cannot fill those evidence gaps. Integrated accepted cells stay
zero. Earlier immutable panel readers retain their original scope and do not
automatically invoke this new reader.

Limits: at most 8,192 total native word/virtual spans and 262,144 native segment
memberships; at most three referenced rows per span, with existing native/cell
and viewport input limits. Checkpoints run per native display and span. Callers
must enforce output/time budgets. Private captions, headings and profile data
must stay out of Git. The reader starts no app, audio, model or device.

The guarded probe uses CPU14, BelowNormal priority, one math thread, GPU off,
the existing model-free helper lock, a 12-minute bound and campaign disk/private
allowances. It verifies exact D1 owners/heartbeats and protected bindings before
and after; it does not alter numerical ownership or bound code. Fresh attempts
retain owner, four source snapshots and any failure. Thirteen tests use actual
independent readers and unchanged pure application span/casing methods with
synthetic process/clock/geometry/native data and copied closure metadata inside
new fixtures. Hand-calculated arithmetic, negative intervals, null stages,
empty-caption denominators, ambiguity, finality, row membership, nonfinite
clocks, budget limits and evidence changes are covered. These tests are not new
application measurements or audio evaluation.

Choose a fresh output directory; run outside exclusive paced measurements.
PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_timing.py" --output "$jpLocal\n4\application-timing-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_timing.py" --output "%JP_LOCAL%\n4\application-timing-probe-v1"
```

Internal API, after independent production plan/run admission:

```python
from review_application_timing import review_cell
private_review = review_cell(stopped_cell_folder,
    checkpoint=bounded_evaluator_guard, **verified_cell_expectations)
```

Probe outputs are `PROBE_OWNER.json`, immutable `source/` snapshots,
`ADMISSION.json`, private `tests/`, `tests.txt` and `RESULT.json` or `FAILED.json`.
No production plan, panel or timing acceptance receipt is created by the probe.
