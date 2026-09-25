# Native caption to recorded widget content

Purpose: `review_native_widget.py` connects complete native caption histories to
the strings and visibility facts recorded by the existing viewport collector.
It independently reruns the qualified native caption and viewport reviews,
checks their source clocks, and compares each changed row and each span's first
visible, first final visible and latest recorded state with compatible earlier
native publications. Raw words, finality, source support, span identity and
speaker metadata must match. Applied caption strings must also match the
primary application's casing and formatting rules. Heading strings are carried
forward exactly as recorded; they are not verified person identities.

Inputs: a stopped native session, verified audio-only job, complete native
envelope, bound viewport SUMMARY.json, qualified application source receipt,
fixed display roster (`[{"id": "...", "name": "..."}]`) and `open_with_names`
primary mode. Its caller must independently reconstruct application ownership,
source lineage, actual prepared roster and primary settings using the V2 cell
reviews. The caller-supplied roster is not independently admitted here and must
not contain evaluator truth. Closed modes, manual edits, archived formatting
and optional text assistance require separate contracts.

Output: an in-memory private `PASS_NATIVE_WIDGET_PRIMARY_CONTENT_JOINS_ONLY`
result with content joins, first/final/latest references, missing native spans,
never-visible and no-final-visibility counts, recorded headings and evidence
bindings. The widget log has no consumed native publication ID. Consequently,
all compatible predecessors are retained through counts, ranges and a hash;
ambiguous matches stay explicit. Even a unique content match does not prove
which event the application consumed. This result does not qualify latency,
naming accuracy, continuous exposure, physical scanout, application ownership,
production coverage or N4 acceptance. Integrated accepted cells remain zero.
Private transcript and heading data must never enter Git or public reports.

The reader imports only the unchanged pure `app/casing.py` from the bound source.
It mirrors the Controller's segment formatting seam without importing the
Controller, UI or model runtime. Limits include 262,144 indexed fragment states,
16 MiB cumulative formatted strings and 32,768 changed rows, plus the existing
native/viewport limits. Production callers must supply a bounded checkpoint
and enforce a private output allowance. Sparse observations retain their
sampling interval and missing-state denominators; they are not continuous
visibility measurements.

The guarded probe uses CPU14/BelowNormal, one math thread, no GPU, the helper
lock, disk/private allowance and a 12-minute limit. It verifies the exact D1
owners, fresh heartbeat and protected bindings before and after. Each fresh
attempt preserves its owner, source snapshots, admission and test output;
failures are never overwritten. Twelve tests exercise raw/applied text
corruption, clock order/origin, missing visibility, ambiguous identical states,
recorded labels, casing, split formatting fallback, primary mode, index bounds
and changed evidence. Positive fixtures call the unchanged native pure span
state and casing methods. All events, geometry and clocks are synthetic; no
audio, widget, model, microphone or Pi starts. Passing these checks qualifies
only this development helper, not a real application run.

Attempt v1 preserved eleven passing tests and one fixture assertion failure:
token replacement in a reused row does not constitute row retirement. The v2
positive fixture adds an explicit empty viewport observation to exercise the
collector's actual removed-row record. The production reader is unchanged;
the v1 source snapshots, admission, test log and failure remain intact.

Run only outside exclusive paced measurements, with a new output directory.
PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_native_widget_review.py" --output "$jpLocal\n4\native-widget-review-probe-v2"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_native_widget_review.py" --output "%JP_LOCAL%\n4\native-widget-review-probe-v2"
```

Internal API after independent V2 cell and roster admission:

```python
from review_native_widget import review
private_join = review(session, job=verified_audio_only_job,
    expected_envelope=joined_cell['transport']['native_envelope_review'],
    viewport_summary=verified_viewport_summary, source_receipt=verified_source,
    people=verified_display_roster, mode='open_with_names',
    checkpoint=bounded_evaluator_guard)
```

These identifiers stand for independently verified inputs. Compose this helper
explicitly; do not edit earlier bound cell or panel reviewers.
