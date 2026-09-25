# Actual Controller labels versus mode descriptions

Source inspection and downstream consumer tests, 2026-09-25. This extends
MODE_POLICY_FINDINGS_V1.md without changing the frozen application, models,
thresholds, galleries or existing comparison inputs. Source receipt SHA-256:
`8050c8bee52a6ec83c95f3514cb81219c3664dd43e172a477d35a54888e610d5`.

`app/mode_policy.py` describes selected_focus as "Selected names · one Unknown"
and records unknown_policy=constant. However, `app/controller.py:977-980`
special-cases only enrolled_names to a constant Unknown. selected_focus reaches
the general branch, whose fallback is the caption fragment's anonymous_label.
The actual Controller consumer/snapshot tests reproduce numbered Speaker labels
for rejected selected-focus names in sealed component-mode output. The primary
tests use strict=False, retaining every caption fragment. This is an existing
product discrepancy; the published mode description is not evidence that the
Controller implemented it. Other spatial modes share the source branch but
have not been exercised by these five-mode checks.

The closed-mode projection retains a separate distinction. A selected valid
closed_display_assignment produces a display_profile_id and an "assumed" label,
but profile_id remains absent unless the acoustic naming state is confirmed.
The downstream consumer tests reproduce this behavior for N2 closed assumptions.
Scoring must not convert a displayed assumed name into confirmed recognition or
adaptation evidence. The earlier baseline-versus-N2 missing-voice fallback
difference remains recorded in MODE_POLICY_FINDINGS_V1.md.

Eight tests passed for actual Controller construction, backend/mode switching,
real caption-consumer delivery and snapshot text/label projection, including
constant versus numbered fallback, closed assumptions, raw/final text, altered
input rejection and owner/thread cleanup. README_CONTROLLER_PROJECTION.md
documents their inputs, outputs, bounds and PowerShell/CMD/Anaconda commands.
The isolated read-only research roster view validates the full fixed available
selected roster; it creates no personal profiles or enrollment. Initial test
failures from its missing gallery accessor were corrected before the passing
test run; this did not alter application source.

This evidence concerns replayed, already-published modeled display records.
Actual Controller host consumption timestamps measure only the replay. They do
not establish first-visible caption timing, widget delivery, upstream event
publication or complete coupled-inference parity. Preserve the actual projected
labels when evaluating the unchanged version. Any product correction requires
a fresh source derivative and matched retests; it cannot overwrite this evidence
or silently relabel the baseline. Integrated acceptance remains zero.

The full downstream probe subsequently passed all 160 prepared cases at
06:28:18 UTC, including 32 selected-focus cases. Every selected-focus case
contained at least one numbered anonymous fallback after Controller projection.
CONTROLLER_PROJECTION_CHECK_V1.json binds the exact private result and code.
The two smoke sources are reused across catalog/mode/tap factors; 32/32 here
is a development-case census, not a population accuracy estimate or a rate of
misidentification. No accepted application release was changed.
