# Observed-name diagnostics and fixed identity controls

Purpose: `score_observed_names.py` compares recorded GUI heading categories with
the separately admitted evaluator reference join at first visible, first final
visible and latest native-span observations. It computes counts and conditional
rates independently for active and history panes. Fixed identity IDs are never
permuted to maximize agreement, and backend proposals never replace GUI strings.

Inputs: a qualified reference context, an independently reviewed observed-heading
result and its exact bound application payload. `score_cell` invokes the reference
join again before scoring. `project`, `classify` and `summarize` are internal
development seams and do not admit production inputs by themselves. Existing
qualified source, runner and panel wrappers stay unchanged; a future complete
panel scorer must explicitly call this API and retain its input bindings.

Output: private `SCORED_ESTIMATED_SUPPORT_NAME_DIAGNOSTICS_ONLY` with counts,
rates, conflicts, revision-count availability, input fingerprints and controls.
The unit is a **native lexical span at an observation stage in one pane**,
including retired/changed hypotheses. Empty-caption virtual IDs are counted and
excluded from lexical denominators. No output is reference-word accuracy, speech
duration, an enrollment decision or a new actual GUI observation.

A complete reference with exactly one intersecting estimated identity receives
an available-profile or outside-available-profile category. A visible exact name
can then agree or disagree with that fixed identity. All other reference support
remains unresolved, including overlap, incomplete target references, no activity,
and out-of-file or zero-width native windows. Native revision windows and estimated
activity do not prove phonetic word identity: even the single-person rates below
are conditional diagnostics, not certified naming accuracy.

Each pane reports:

- Correct/wrong visible available name counts divided by all spans with one
  estimated available reference identity, retaining missing/offscreen spans.
- Visible known names on a single outside-available identity divided by all such
  spans. Missing E members may be in this group; it is not a genuine-outsider rate.
- Visible Unknown divided by all native lexical spans, and separately by jointly
  visible heading/caption opportunities. Zero denominators yield null rates.
- Reference-support, heading-kind and outcome counts, missing stages and
  non-joint visibility. Forced assumptions never receive recognition credit.

Suppressed, absent, pending, anonymous, unrecognized and ambiguous strings remain
distinct from Unknown. One pane's visibility cannot support another pane. Conflicts
retain both results with no chosen winner. Any visible glyph is the collector's
threshold, so neither a whole name nor every word is proven visible. Revision sums
are over native spans and may count one row change for multiple spans; they are
not distinct physical paints, elapsed exposure or changes per second.

Controls replace labels only at **already jointly visible observed opportunities**
while holding missing/offscreen/suppressed geometry fixed. `all_unknown` assigns
Unknown; `constant_name` uses the lexicographically first available profile ID,
chosen without reference accuracy. Empty galleries make the constant control
unavailable. These are diagnostic counterfactuals, not separately rendered GUI
runs, and cannot predict geometry or feedback from another name policy.

The guarded probe reconstructs the actual qualified reference context and scores
the saved synthetic GUI observation, plus hand-computed fixtures. Eighteen tests
cover correct/swapped/constant/Unknown names, forced choice, missing visibility,
pane conflict, core/display disagreement, unresolved support, empty populations,
revision-count availability and changed/foreign evidence rejection. No waveform,
model, window, microphone or Pi is opened. Private profiles and transcripts never
enter Git or the application. Known-track fragmentation, returning-person
consistency, exact acquisition, continuous wrong-name exposure, full-panel naming
and stage acceptance still need their own supported evidence and implementation.

The probe uses CPU14, BelowNormal, one math thread and GPU off, the existing helper
lock, a 12-minute/8-MiB output bound, disk floors and shared private allowance.
It verifies D1 exact ownership/heartbeat/bindings before and after. Use a fresh
output suffix outside exclusive application/resource measurements. Attempts retain
their owner, four source snapshots, admission and any failure.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_observed_name_scoring.py" --output "$jpLocal\n4\observed-name-scoring-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_observed_name_scoring.py" --output "%JP_LOCAL%\n4\observed-name-scoring-probe-v1"
```

Internal evaluator API after independent observed-cell admission:

```python
from naming_reference import load_qualified_context
from score_observed_names import score_cell
context = load_qualified_context(checkpoint=bounded_evaluator_guard)
private_score = score_cell(context, verified_observed_heading_review,
                           exact_admitted_payload, checkpoint=bounded_evaluator_guard)
```

Private outputs: `PROBE_OWNER.json`, `source/`, `ADMISSION.json`, `tests.txt`,
`SYNTHETIC_NAME_SCORE.json` and `RESULT.json` or `FAILED.json`. Public qualification
contains only bindings, counts and declared scope. No actual N4 cells are accepted
by this development probe, and no release or default is promoted.
