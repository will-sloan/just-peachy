# Task 02 — Calm captions and touch UI

**Implemented locally, 20 September 2026.** Existing Tk/Phase 6–7/PROTO1
pipeline retained. No new research, model/library, microphone capture, enrollment,
commit/push, Word edit or replacement release export. Task 03 was not started.

## What changed

- Compact **21px** default; retained Normal 25 / Large 31 / Extra large 37px and
  saved preferences. Tighter line/paragraph gaps, 48px minimum actions, 60px nav.
- Stable native S7 row IDs/marks survive active ownership-segment replacement.
  Only changed text spans are edited. Adjacent supported same-track tokens
  within one utterance can share a heading; Unknown and handoffs stay separate.
  Reading history stays anchored; **Back to live** resumes following.
- **Immediate** text default; optional **150/300ms** fixed-deadline GUI batching.
  Continuous partials cannot reset its deadline. One latest snapshot is buffered.
- **••• · collecting voice** has a **1.2s deadline**, resolved on the next
  applied display update (80ms poll, chosen smoothing and OS scheduling extra);
  stable names require **200ms** of unchanged display evidence. Disagreement
  removes the old name on the next applied snapshot. Explicit unavailable
  evidence is separate. Text never waits for identity. Late supported names
  remain possible. Raw tentative identities/scores remain in Diagnostics/logs.
- Generic **Unknown** ordinary default. **Settings → Advanced → Numbered
  anonymous labels** retains the existing numbered variants. This changes only
  presentation, including in Anonymous; native track inference stays intact.
- Active mode in header; small **Show all** only when strict Selected-focus
  hiding is enabled. Active tabs highlight separately from Start/Stop. Consistent
  Back, compact Settings choice rows, long People names safely shortened in the
  list, full names retained in their profile. Enrollment keyboard unchanged.
- Optional **145px** beam panel: focused/scanning/output shapes and colour keys,
  selected fresh output ring, estimated voice-position dots, solid/fresh versus
  dashed/hollow stale, board frame and 90° front/rear fold. Tap it to collapse;
  re-enable in Settings. Idle truthfully shows **No fresh direction**.
- Settings explains the actual active recipe, O0 ASR output (+3dB once live)
  and O1 processed automatic output (unity). All prior modes/recipes/taps remain.

`app/ui.py`, new `app/caption_display.py` and `config/ui.json` implement the UI.
The controller only adds detached ownership/identity metadata, bounded recent
decision diagnostics and two validated display preferences. The complete
vendor pipeline, live capture/timing adapter, model manifests and all non-UI
configuration match the saved pre-task-02 baseline. Raw transcript/model outputs,
endpoint rules, existing enrollment storage and task 01 repairs are unchanged.

## Verified results and scope

| Check | Result |
|---|---|
| Software/widget regression suite | **166 passed**, 0 failed/skipped; 13.97s. Includes task 01 timing/Stop and enrollment/storage contracts. |
| Exact portrait / comfort | Native Windows client **480×800** and **600×1000 at 125%**, 96 DPI, per-monitor awareness 2; inspected real screenshots. |
| Pending/grouping/scroll/layout | Synthetic tests cover label churn, native segment replacement, pending→name→Unknown, unavailable voice, long text/names, empty/populated pages, scroll extent, navigation and zoom preserving the deadline. |
| Short GUI timing fixture | 12 synthetic revisions per choice: 12/4/2 render batches for Immediate/150/300ms; raw inputs unchanged. |
| Measured first-change → widget maxima | **1.70 / 157.17 / 310.01ms**. Existing 80ms polling and OS scheduling are separate. No hard real-time or WER claim. |
| Actual native saved-file GUI | Existing **6.0045625s** prepared O0 speech; **PASS**, 10.68s wall; final words/IDs matched backend, 14 observed revisions, all pages reachable, clean controller/worker close. |
| Resources | Native process at stop: **479.36MiB RSS**, **5.67 CPU s**, one ASR and one speaker load. GUI-only fixture: **46.41MiB peak process RSS**, **0.875 CPU s**, **6.14s wall** including screenshots. Windows screenshot helper child usage excluded. |
| Device/privacy | No microphone/playback/USB capture; five valid render-default observations unchanged. Fresh private test data root; production people/settings/vectors untouched. |

The zoom check initially exposed a stale child-layout screenshot and a renewed
identity deadline on UI rebuild. Both were fixed and the relevant checks/native
file run repeated. Preliminary receipts remain private; the final source-bound
checks are `UIITER2_02_CHECKS.json`. No broad sweep was run.
After native verification, one Settings sentence was clarified to include the
chosen smoothing interval in pending-label refresh. The final suite covers
that source, a fresh real Settings screenshot used zero model loads/streams,
and closeout verifies that exact sentence is the only UI-code difference from
the native/timer receipts. Speech inference was not repeated for a copy edit.

Real app screenshots: [idle](evidence/uiiter2_02/real/00_real_idle_no_fresh_direction.png),
[native captions](evidence/uiiter2_02/real/02_native_final.png),
[empty People](evidence/uiiter2_02/real/03_real_people.png),
[Settings](evidence/uiiter2_02/real/03_real_settings.png),
[125% comfort](evidence/uiiter2_02/real/04_real_comfort.png).
Explicit **MOCK** fixtures: [long name](evidence/uiiter2_02/mock/03_long_name_MOCK.png),
[accessibility](evidence/uiiter2_02/mock/05_accessibility_MOCK.png),
[fresh/stale beams](evidence/uiiter2_02/mock/06_fresh_and_stale_beams_MOCK.png).
No synthetic identity is preloaded into the application.

## Launch, inputs and outputs

Close any older prototype instance first. From the repository root
`C:\Users\amiri\Documents\GitHub\just-peachy`, PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

It opens idle. Start uses the existing consented XVF input flow. For immediate
visual comparison choose Settings → Compact / Immediate; an older saved font
preference intentionally takes priority over the new default. Prepared-file
input uses the existing file picker or `main.py gui --wav "C:\path\O0.wav"`.
Inputs remain the existing private profile store and external checkpoints;
outputs are the existing captions/private journals plus display preferences.
No training assets or private vectors belong in the source package.

Test reproduction, inputs/outputs and both shell forms are maintained in
`app/README_CAPTION_DISPLAY.md`, `tests/README_CAPTION_DISPLAY.md`,
`tools/README_CAPTION_PRESENTATION.md` and `UI_ITERATION.md`.

## Exact local rollback

The **pre-task-02** archive includes completed local task 01 fixes:
`Resumes\.uiiter2_02\prototype_before_02.zip`, with per-file baseline hashes.
Do **not** reset to Git HEAD: that would also lose the uncommitted task 01 fixes.
After closing the prototype, from the repository root run the dry-run and then
the explicit restore if desired (PowerShell):

```powershell
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_02\restore_before_02.py
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_02\restore_before_02.py --apply
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B Resumes\.uiiter2_02\restore_before_02.py
.edge-speech-env\python.exe -B Resumes\.uiiter2_02\restore_before_02.py --apply
```

It checks the archive and current source hashes, refuses later edits, restores
only task 02 modified baseline files, and moves new Python helpers/tests to a
verified private backup. New docs/evidence remain as historical records.
It does not alter models, user data or old exports. Only the dry-run was tested
against the working prototype; no rollback was applied.

## Remaining limits

Human real-room caption/identity comfort and a physical touchscreen are
**AWAITING_USER**; new personal enrollment and CM5/ARM64 operation are
**NOT_TESTED** here. The bounded task 01 hardware evidence remains separate.
The shared source is still Windows/CM5 code; no newly packaged export or hardware
qualification is implied. UI smoothing/pending rules change presentation only,
so they do not establish improved recognition or make angle evidence identity.
