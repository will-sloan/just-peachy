# Selected closed-group captions — field fix, 21 September 2026

The user reported Unknown labels in **Selected · closed group (Always assign)**
and explicitly chose: always use a selected name, marked assumed when evidence
is missing. The previous implementation forced only fresh, clean voice matches;
S7 unowned caption fragments and the ordinary UI pending timer could still show
Unknown. This update corrects that display contract in the existing pipeline.

## What to expect

Choose Mode → Selected · closed group → compatible enrolled names → Apply.
Every **new** caption now immediately has a selected name. A supported voice
name retains its existing accepted/forced status. Without supported caption
ownership, the app shows **Name · assumed**. It prefers existing same-track or
same-utterance voice evidence, then a preceding voice winner within2s. When no
usable match exists at all, the first compatible selected-gallery entry is an
arbitrary, explicitly assumed roster fallback. Later voice evidence can replace
it. Overlap and unselected visitors can be misnamed in this intentional mode.

Raw known-profile ID, voice availability, naming state and scores are preserved.
`closed_display_assignment` carries the display-only UUID, basis, event IDs and
null acoustic confidence. It neither certifies an identity nor updates enrollment,
session reference banks, live speaker directions, ASR text or word timing. A
failed optional identity helper still reports failure/unavailable evidence;
the assumed label does not mean that helper is healthy.

The200ms pending/name-stability timer no longer substitutes Unknown in this
closed display. Open-set, spatial and assigned-seat modes retain their existing
rules. A missing/deleted/incompatible roster still blocks a fresh Start; changing
people invalidates current assumptions. Previous archives are not retroactively
re-guessed. The new separate provenance is retained in session event payloads.

## Launch

Use the existing **Just Peachy Prototype** desktop shortcut, or PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

The GUI opens idle; select the roster and press Start when ready. Existing
models/profiles and Windows/CM5 source layout are retained. No new model,
dependency, threshold tuning, training or research campaign was added.

## Verification

**329 software tests passed**, zero failures/errors/skips,37.58s, including eight
additional regression cases for this field correction.

The accompanying CLOSED_GROUP_DISPLAY_CHECKS.json binds the final software and
native receipts. New contracts cover no-vector/overlap assumptions, causal
same-utterance/recent fallback, first-roster fallback, later voice changes,
open-mode isolation, raw identity separation, people invalidation, unavailable
identity after enhancement failure and immediate actual Tk caption display.

Two12-second native cases reuse task04's already-qualified public CMU fixture
profiles/query, with real ASR/segmentation/ReDimNet and shared model instances.
Closed case:84 caption updates /118 segment updates,56 separate display
assumptions, zero missing selected-name assignments. Open selected-A case on
the same B audio:89 caption updates /123 segment updates; B remained unnamed
and no closed-display assumption was added. Both completed in27.82s total;
fixture reference files were unchanged. The actual480×800 portrait screenshot
was inspected. This demonstrates the display contract and pipeline completion,
not improved speaker accuracy, overlap correctness or CM5 qualification.

No microphone, audible playback or production-gallery edits were used. The
private checkpoint/evidence is `Resumes/.closed_group_fix_20260921` (303 source/
configuration/document files before this fix). The existing task01–12 receipts
remain historical. The current source is updated; task08's immutable release ZIP
was not rebuilt. No automatic commit/push.

For reproduction inputs/outputs and commands see ../app/README_ROSTER.md,
../app/README_CAPTION_DISPLAY.md, ../tests/README_ROSTER.md and
../tools/README_ROSTER.md. The exported MODE_MATRIX.json keeps all54 default
profiles and four strong-seat variants unchanged, with revised mode semantics.

The canonical MODE_GUIDE.md was open in Word and Windows refused writes.
An updated complete copy is provided as **../MODE_GUIDE_UPDATED.md**; the open
Word document and any unsaved edits were left alone. MODE_SEMANTICS.md and app
help text are updated. The ordinary alternative if assumed labels are unwanted
is **Selected names · one Unknown**; that mode's recognition policy is unchanged.
