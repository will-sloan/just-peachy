# UIITER2 task 03 — Linked sessions, exact audio and resources

Implemented locally on 20 September 2026. **185 software checks PASS** plus
one short real-model prepared-file check PASS. Task 01/02 changes are retained.
This task is complete at the bounded software/native-file acceptance level;
physical playback, human usability and CM5 remain NOT_TESTED. No task 04 work,
dataset sweep, new model/library, automatic commit/push or master Word edit.

## What changed and how to try it

Launch from `C:\Users\amiri\Documents\GitHub\just-peachy` in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD or Anaconda Prompt from the same folder:

```bat
prototype\Start-Prototype.cmd
```

Settings → **Developer Sessions** supplies New text-only, consented New + exact
audio, Stop, Save/pin, reopen, rename, problem notes, separate user corrections,
privacy-confirmed text/full ZIP export, confirmed Delete, explicit listening
output selection and caption-interval playback. Press Start separately to
capture; opening the app or creating a draft does not start a microphone.
Audio recording has a visible indicator. New preserves the previous draft;
Save pins it. A subsequent Start after Save or opening history makes a new
text-only draft. Existing modes/recipes/taps and cached models remain intact.

The same capture feeds ASR and identity. Start/Stop/mode transitions create
distinct source epochs without adding a microphone/model path. Listening fully
stops/drains capture first and is blocked during enrollment; Start or enrollment
stops listening before opening input. No default PC output is selected/changed.
Choose a specific output in Sessions; unsupported 16k mono endpoints fail visibly.
The physical playback check was left unperformed because no listening endpoint
was selected by the user for this task.

`app/sessions.py` provides a bounded asynchronous archive, immutable event log,
SQLite offsets, crash recovery and retention. `session_controller.py` coordinates
existing ownership; `session_playback.py` supplies explicit-output listening;
`session_ui.py` supplies touch pages. Small changes in `buffers.py`, `pipeline.py`,
`controller.py` and `ui.py` attach the side sink and workflow. The lifecycle
test double was updated for the real engine interface. New session tests and
native/check/export tools have dedicated README run/input/output instructions.

## Data contract and exact paths

Normal new conversations resolve to:

```text
C:\Users\amiri\JustPeachy\data\conversations
```

`JUST_PEACHY_DATA` overrides the default. No production profiles or conversations
were changed by the checks. The verified fixture conversation is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Resumes\.uiiter2_03\native_final\conversations\c5cae3099f3940cd83d369c4da835864
```

Its exact audio and linked evidence are under:

```text
epochs\7325ffb58e2e484a800e1306c0232ada\model_input.f32le
epochs\7325ffb58e2e484a800e1306c0232ada\epoch.json
epochs\7325ffb58e2e484a800e1306c0232ada\events.jsonl
epochs\7325ffb58e2e484a800e1306c0232ada\windows.jsonl
epochs\7325ffb58e2e484a800e1306c0232ada\resources.jsonl
epochs\7325ffb58e2e484a800e1306c0232ada\captions.sqlite
```

The master is headerless little-endian float32, mono 16k, with no quantization
relative to model input. It is post-XVF/pre-model audio, not raw microphones or
all focused beams. O0 gain remains once upstream; prepared O0 is not gained
again, and O1 remains unity. ASR/identity use the same source. Source-backed model
windows reproduce half-open indices and declared segmentation left padding.
On-demand `.npy` + JSON exports require a pinned source; no overlapping window
library is duplicated. `tools/README_SESSIONS.md` includes the exact CLI commands.

Immutable raw ASR and identity/revision events remain separate from provisional
casing, final punctuation and user corrections. Indexed stored formatting
survives restart/rebuild. Caption/audio links are coarse utterance intervals,
not word alignment. Original mode/recipe/tap/roster, effective profile, capture
metadata, software/model hashes, gaps and distinct source/host/availability clock
fields remain in the archive. Reopened captions use the current GUI naming mode;
historical native identity/name events are retained for analysis.

## Bounds and privacy

Text-only is default. Explicit participant consent enables exact audio for that
conversation. Local data/exports are sensitive and unencrypted; no upload occurs.
Text ZIPs omit audio/vectors/roster; full ZIPs include them. Neither export is
automatically placed in version control. Delete cannot remove enrolled people.

Linked archive target is 2 GiB with a 2 GiB free-space floor, 10 inactive unpinned
drafts, and per-epoch payload caps of 256 MiB audio / 64 MiB metadata. SQLite and
manifest overhead mean this is not a byte-exact reservation. Float32 mono16k is
219.73 MiB/hour; the audio cap is about 69.9 minutes. Full export copies occupy
additional storage. Save/pin prevents automatic cleanup; explicit Delete remains
available. Oldest unpinned inactive drafts may be removed at the next admission.

Writer queue is capped at 512 items / 4 MiB; no disk/inference is added to the
PortAudio callback. Slow/full storage stops archival with visible loss/partial
status while the independent live caption path can continue when feasible.
Recovery preserves complete float samples and marks unknown/missing tails;
it never pads gaps into PASS. Final/periodic fsync and atomic metadata improve
recovery, but physical power-loss durability was not tested. Existing native
pipeline storage failures can still stop capture. UI/export/retention details
and all bounds are in `app/README_SESSIONS.md`.

## Executed checks and limits

| Check | Result |
|---|---|
| Full software suite | 185 PASS; 0 failures/errors/skips; 17.45s |
| New session coverage | 16 archive/controller tests + 3 real-Tk/stub touch tests |
| Exact native source | 96,073 float samples / 6.0045625s; bytes identical to existing prepared speech source; no second gain |
| Native lifecycle | 10.24s wall; one ASR load, one speaker load, one stream; New reused cache; restarted browser loaded no models |
| Indexed evidence | 16 actual embedding/segmentation window references; 17 separate formatting events; exact slice/padding exports including CLI |
| Resource joins | 8 samples, 1.008–1.092s intervals; source epoch/cursor + host clocks retained |
| Process observations | Maximum sampled RSS 445.98 MiB; process CPU counter 4.203s at last sample; these are short Windows observations, not overhead/power or CM5 estimates |
| Save/restart/reopen/play | PASS through fake explicitly chosen output sink with exact corresponding caption samples and capture release assertion |
| Storage/retention | Queue pressure and disk-full injection, real child-process abrupt exit, torn-tail recovery, pin protection, rename/export/delete/correction separation PASS |
| Portrait UI | Actual native-backed 480×800 screens visually reviewed; touch consent/delete/output/status checks PASS |
| PC output defaults | Five read-only observations unchanged; no audible playback |
| Human/physical/ARM64 | New live-mic/archive hardware run, real endpoint playback, physical touch and CM5 NOT_TESTED |

Screenshots: `docs/evidence/uiiter2_03/`. Raw audio/vectors/logs stay private in
`Resumes/.uiiter2_03`. `UIITER2_03_CHECKS.json` binds source/test/artifact hashes.
No WER, speaker accuracy or resource improvement is claimed by these checks.
Vendor inference code, model/profile/config assets, task 01 capture timing,
task 02 caption renderer and personal store implementation are unchanged from
the pre-task snapshot. Existing 0.1.4 release ZIPs remain historical; use the
updated checkout now and rebuild through the existing release procedure later.

## Rollback

The before-task ZIP preserves the completed **local task 01/02** source, not
just git HEAD. Close the GUI and all checks. From the repository in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_03\restore_before_03.py
# After reviewing the dry-run plan:
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_03\restore_before_03.py --apply
```

In CMD / Anaconda Prompt, use the same commands without `&` and without the
PowerShell comment line. The script verifies hashes, refuses later edits,
restores task 03 changed pre-existing files, and moves new Python modules to a
private rollback backup. New docs/evidence stay as historical records. It never
touches people/conversations/models. Only the dry run was executed.
