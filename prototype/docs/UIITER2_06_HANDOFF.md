# Task 06 — Paragraph enrollment and honest progress

Completed locally on 20 September 2026, on top of tasks 01–05. **242 software
checks PASS; 11 bounded native checks PASS.** Human/XVF enrollment, physical
touch and CM5 remain **NOT_TESTED / awaiting participation**. No unattended
enrollment, audio playback, training, sweep, model/dependency change, release
rebuild, automatic commit/push or Word edit occurred. Stop here; task07 is not
started.

## Launch and use

From `C:\Users\amiri\Documents\GitHub\just-peachy`, PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Open **People → Add person** (or an existing person → Add a reference session).
Keep the intended O0/O1 tap. Choose 15/30/60 **Target: unique usable speech**, or
the fourth **Read paragraph → Done** option. Edit the existing guide if desired,
consent and Start. Timed goals may need additional different natural speech.
Done has no timed/verbatim requirement; tap **Done · check reference** when
finished, inspect the drained quality result, then Save if enabled. Free speech
and an empty guide remain valid. Existing people/UUID/reference operations and
all caption, roster, recipe, tap and spatial modes remain available.

The new option is its own toggle. Timed mode omits offered-text metadata and the
optional ASR estimate. There is no separate threshold slider or new model choice.
See `ENROLLMENT_GUIDE.md` for the full human procedure.

## Actual changes

- `app/enrollment_quality.py`: unchanged 10s segmentation / disjoint 0.5s
  embeddings, thresholds and averaging; accepts paragraph `target_sec=None`,
  validates finite vectors, publishes completed-window counts and enforces
  contiguous, idempotent source offsets. An exact repeated source block cannot
  add usable time or inference. Repeated words newly captured at new times are
  different support; this is not an acoustic replay detector.
- `app/enrollment_progress.py`: standard-library ordered word-match estimates
  and UI-only interpolation. No script input to speaker inference. No aligner,
  dictionary, hotword bias, training or inference per animation frame.
- `app/controller.py`: one capture owner and bounded quality queue; optional
  stream shares the resident ordinary Sherpa model. Estimates run after existing
  quality blocks, with final drain on Stop. Optional ASR failure is visible but
  cannot reject valid voice evidence. DRAINING/ANALYZING are visible before joins;
  Save requires READY. Capture closure no longer depends on queue submission
  succeeding. Source gaps/repetition fail explicitly.
- `app/people.py`: supports and persists paragraph references through restart
  and import/export while preserving old timed-profile validation. Stores
  offered text/hash only for paragraph mode, clearly reference-only; saves raw
  ASR endpoint text/IDs/source bounds, quality, support/hash and integrity receipt.
  No raw reference WAV is retained; metadata alone cannot recreate it.
- `app/ui.py`: four touch options, unchanged editable paragraph, honest captured
  activity/backlog versus verified speech, smooth bounded bar, Done/Save controls
  above the guide. Paragraph bar explicitly shows verified share of captured
  audio, not a fulfilled quota. Existing 80ms poll and physical 480×800 client.
- New focused tests/native helper and their READMEs; existing unit runner now
  collects destroyed Tk test cycles on the main thread before subsequent cases.
  This fixes the initial regression-run `Tcl_AsyncDelete` abort; it does not alter
  the application's model runtime. That aborted run has no PASS claim.

The technical paragraph floor is **one admitted 0.5s window**, matching the
installed audio adapter, plus clipping ≤0.005, consistency ≥0.3, clean speech
support and gap-free capture. References below 15s say **limited evidence**.
This reuses the shortest existing timed goal as a UI warning; it is not a newly
tuned identity threshold. Brief evidence may perform poorly in real conditions.

## Executed checks and resources

| Check | Result / actual observation |
|---|---|
| Complete software regression | 242 passed, zero failures/errors/skips; 25.941s. Includes existing cleanup, storage, roster, seats, captions and live-source doubles. |
| Before/after genuine audio parity | Same 12s task04 CMU recording; baseline/timed/Done vectors bit-identical, max absolute delta **0.0**; identical intervals, quality and call counts (2 segment, 24 embed calls per variant). |
| Shorter-than-target behavior | 12.0s verified usable; Done can Save, 15s target cannot. Limited-evidence status retained. |
| Ordinary ASR / unrelated guide | 39 recognized words; estimated coverage 10.87%, agreement 11.76%. Low match does not change vector or acceptance. Source text remains private. |
| Save/restart/export/import | Actual native vector, new-process UUID reload, compatible gallery restored; wrong tap and duplicate saved source rejected. Fixture stores isolated. |
| Negative evidence | Native too-short, silence and clipping rejected; model-double overlap, corruption, gaps and duplicate support checks passed. No claim of a native overlapping-speakers accuracy study. |
| Actual Tk | Four fixture screens inspected; target/consent/Done/Save and backlog visible at 480×800. Stub data is explicitly labelled; not a microphone check. |
| Native check resources | **4.633s wall, 6.375 CPU-seconds, 433.62 MiB peak process working set** on this Windows desktop; one ASR load, one speaker-model load, one ASR stream. This includes checks/model load/hash verification, not a live throughput benchmark. |

Final private evidence is in `Resumes\.uiiter2_06\native_final`, `unit_final_v2`
and `ui_final`. Compact bindings/results are `UIITER2_06_CHECKS.json`; small
fixture screenshots are under `docs/evidence/uiiter2_06`. All eight installed
asset hashes were verified; vendor models, recipe/config files, live audio and
timing adapters, session archive and caption policy stayed unchanged.

## Limits and remaining human check

The first read estimate waits for the existing 10s chunk (or earlier Done), and
may lag under load. ASR analyzed time makes that visible. Ordered word agreement
is approximate, may revise and does not establish verbatim reading or identity.
Saved segment bounds are decoder endpoints, not phoneme/word timestamps. There
is no evidence here of stronger embeddings from knowing the script, improved
field recognition or CM5 performance. Local ReDimNet input is audio-only
`float32[1,num_samples]`; exact versions/hashes are in the receipt and the
no-addition dependency ledger. Original licence/asset obligations remain.

When the person is present: choose Done, consent and speak; skip some words;
confirm backlog drains, actual duration/limited status and Save; close/reopen
and try different fresh speech. Compare one timed reference, short silence and
Cancel. Keep O0/O1 references compatible. No person was enrolled while away.

## Rollback

The checkpoint `Resumes\.uiiter2_06\prototype_before_06.zip` preserves all local
tasks 01–05, not merely Git HEAD. Close the prototype first. PowerShell from repo:

```powershell
# Dry run: validate archive, scope and current hashes first.
& .\.edge-speech-env\python.exe -B Resumes/.uiiter2_06/restore_before_06.py
# Apply only when deliberately rolling back task 06.
& .\.edge-speech-env\python.exe -B Resumes/.uiiter2_06/restore_before_06.py --apply
```

CMD / Anaconda Prompt: use the same two commands without the leading `&` and
with `.edge-speech-env\python.exe`. The helper refuses later unreviewed changes,
restores changed baseline files, and moves only this task's new Python files
into a private rollback backup. New documentation/evidence remains historical.
It never edits people, recordings, model assets or the Git index.

**Earlier code cannot read paragraph-mode references.** If you have saved such
profiles, preserve that store and use task06 code to access/export them; do not
delete or falsify their duration to make older code load them. To exercise the
rolled-back code, use a separate empty test data directory with the existing
`--data-root` option. Do not mix older-store editing with the new references.
