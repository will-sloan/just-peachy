# Observed GUI heading interpretation

Purpose: `review_application_labels.py` interprets the heading strings actually
recorded by the viewport collector, keeping them separate from the backend's
proposed identity. It composes the qualified cell, fixed-roster, native-caption,
widget and recorded-timing readers. It reads the already joined snapshot roster
and verifies its fingerprint against the admitted gallery and widget reader.
It binds the unchanged `app/ui.py` and `app/caption_display.py` policy source.
It does not re-execute the stateful GUI labeler or reconstruct unseen headings.

Inputs: a stopped V2 cell folder, a bounded checkpoint and the independently
verified plan/run expectations (`payload`, `plan_sha256`, `coordinator`, child
`code`, `executable`, `coordinator_argv`, `state`). Only the independently admitted
primary open mode is covered. The internal `project`, `interpret_row` and
`label_kind` seams do not admit production input on their own. No evaluator truth,
reference transcript, enrollment identity or fitted label mapping is supplied.

Output: a private in-memory `PASS_V2_APPLICATION_RECORDED_GUI_LABELS_ONLY`
result with the preceding content/timing review and deduplicated heading states.
Each pane retains its actual applied string, visibility, matching fixed-roster
ID (when an exact display-name match exists), native profile agreement and glyph
geometry. Exact string categories distinguish roster names, Unknown, unavailable
voice, pending, numbered anonymous, transcription, suppressed, absent, forced
assumption and unrecognized text. The two Unknown strings retain their exact
different wording. Case changes, truncation and extra suffixes are not silently
normalized into a known name. Roster names colliding with reserved UI strings
remain ambiguous. A forced-roster assumption never becomes verified recognition.

A heading and caption must have observed glyphs in the same pane to receive
that joint-visibility diagnostic. Visible heading glyphs in one pane and visible
caption glyphs in another do not establish it. Different names in the two panes
remain two predictions; no winner is selected. A hidden known name stays in
applied-text evidence without visibility credit. Empty headings remain suppressed
without inheriting a backend name or neighboring row's label. A native profile
disagreement is a diagnostic, not a reason to overwrite the recorded text.

The output covers changed-row observations plus first caption-row visible,
first final caption-row visible and latest states per native span. Missing stages
remain null and unobserved native spans stay in denominators. The collector's
heading-change counts are retained. Counts are **native spans per observation
stage**, including retired hypotheses and empty-caption virtual IDs; they are
not reference-word accuracy or speech-duration fractions. Timing's separate
lexical/empty population remains available in the nested result. Changed-row
records do not count unchanged periodic samples or establish continuous exposure.

Even one visible glyph can make a heading positive. This reader does not claim
the full name, every word, or a physical screen was visible. The first/final
stage names describe caption-row visibility, not first visible name acquisition.
No exact native event, GUI hysteresis replay, inherited suppressed label,
correct-person mapping, naming accuracy, acquisition latency, continuous
wrong-name exposure, complete panel coverage, memory tier or N4 acceptance is
established. Actual naming scoring still needs a separately admitted evaluator
reference join, appropriate ambiguity/missing-reference handling, fixed identity
controls and actual application evidence. Continuity/stop-restart remain open.

Limits: 256 unique roster entries, 1,024 characters per applied heading, 32,768
deduplicated states and 262,144 total state-to-span memberships, plus all existing
native/cell/viewport bounds. Checkpoints run per new/visited state. Callers must
provide output/time budgets. Detailed strings/profiles stay private. No app,
window, model, audio input, device or Pi is started by this reader.

The guarded probe uses CPU14, BelowNormal priority, one math thread, GPU off and
the existing model-free helper lock, with a 12-minute bound and campaign disk/
private allowances. D1 exact identities, heartbeats and bound code are checked
before and after. Fresh attempts retain owner, four source snapshots and any
failure. Sixteen checks use actual readers on synthetic process/clock/geometry/
native data, with unchanged pure application span/casing methods. Additional
explicit pane fixtures test suppression, ambiguous/reserved names, forced choices,
cross-pane visibility, conflicts, clipping, exact spelling, missing stages,
changed evidence and allocation bounds. These are not new GUI measurements.

Use a fresh output directory outside exclusive paced measurements. PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_labels.py" --output "$jpLocal\n4\application-label-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_labels.py" --output "%JP_LOCAL%\n4\application-label-probe-v1"
```

Internal production API after independent plan/run admission:

```python
from review_application_labels import review_cell
private_review = review_cell(stopped_cell_folder,
    checkpoint=bounded_evaluator_guard, **verified_cell_expectations)
```

Probe output: `PROBE_OWNER.json`, immutable `source/` snapshots, `ADMISSION.json`,
private `tests/`, `tests.txt`, and `RESULT.json` or `FAILED.json`. The earlier
immutable panel wrappers retain their original scope; this reader must be
invoked explicitly by a separately qualified caller. Accepted N4 cells remain
zero until the complete stage acceptance requirements are met.
