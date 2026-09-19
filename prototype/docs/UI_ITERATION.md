# Portrait UI development and verification

`app/ui.py` implements `PrototypeUI(root, controller)` on Tk's owning thread.
`app/casing.py` provides stateless display-only casing. `config/ui.json` contains
colors, fonts, sizes, defaults, acronym spelling and the editable enrollment guide.
The UI starts idle, asks for microphone consent, and delegates all capture,
model work, profile storage and retention to the controller. Closing waits for
the controller's `CLOSED` state so the window cannot exit midway through cleanup.

## Run the application

From `C:\Users\amiri\Documents\GitHub\just-peachy` in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
# Equivalent direct entry point:
& .\.edge-speech-env\python.exe .\prototype\main.py gui
```

From the same directory in CMD or Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
.edge-speech-env\python.exe prototype\main.py gui
```

Inputs: the controller snapshot/command interface, versioned UI styles, optional
persisted display preferences and personal profile metadata. A saved-file input
uses `main.py gui --wav "C:\path\prepared-mono16k.wav"`; it is explicitly a replay.
Live input requires the separate device configuration described in
`LIVE_AUDIO.md` and in-app consent. Personal data defaults to
`%USERPROFILE%\JustPeachy\data`; models are external in
`%USERPROFILE%\JustPeachy\shared\models`. See `../START_PROTOTYPE.md` for overrides.

Outputs: portrait captions, status, privacy/consent forms and controller commands.
Display settings persist through `settings_update`. The UI neither writes voice
recordings nor loads neural models. Raw ASR remains available in Diagnostics.

## Edit and relaunch

1. Stop listening, close the window and allow cleanup to finish.
2. Edit `config/ui.json` for palette, caption sizes or the default paragraph.
   Runtime size/theme changes are also available in Settings without reloading
   models. UI preferences saved in the data directory take priority over defaults.
3. Edit layout in `app/ui.py`. Keep the four persistent navigation controls and
   full-caption rescue. Give controls at least 48 logical pixels at 100%.
4. Run the focused checks below, relaunch, and inspect pixel-check and the largest
   caption/high-contrast presets. Do not reuse a preview zoom as pixel evidence.

Call `prepare_dpi_awareness()` **before** `tk.Tk()`. It requests per-monitor DPI
awareness for this process; it never changes the operating system's scale.
Pixel-check requests a 480×800 client. `measure_client()` records native Windows
client size, awareness, DPI, Tk scaling and PPI. Window decoration is excluded.
Comfort zooms 125/150/200% request 600×1000, 720×1200 and 960×1600 clients.
They can exceed a small desktop; return to 100% for an exact portrait check.
Fullscreen on the eventual display is a separate hardware check.

## Focused checks (no microphone, model or personal enrollment)

PowerShell from the repository root:

```powershell
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_casing.py' -v
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_ui.py' -v
```

CMD or Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B -m unittest discover -s prototype\tests -p "test_casing.py" -v
.edge-speech-env\python.exe -B -m unittest discover -s prototype\tests -p "test_ui.py" -v
```

The six casing tests cover expansions/retractions, sentence boundaries, standalone
I/contractions, canonical names, explicit acronyms, mixed case, numbers and raw
preservation. Eight actual Tk tests use an explicit fake backend and cover
480×800 physical client, touch targets, consent/cancel, 20 mode transitions,
stable row marks, late labels/final text, old-scroll retention, strict rescue,
touch name entry, enrollment quality gating, UUID actions, import/export consent,
recipe availability, display changes, asynchronous close and separate consent
for Mark a problem with/without an audio excerpt. The session text retention
toggle appears only when the backend supplies `settings.save_session_text`.
When reported by the backend, Settings also offers completed-session limits
3/10/20, session disk quotas 64/128/256 MiB and RAM history 60/120 seconds.
These map directly to `completed_session_limit`, `session_quota_mib` and
`ram_horizon_sec`. RAM changes apply to the next session. Personal references
and pinned problem evidence remain outside rolling session cleanup.

Mark a problem is reachable from Settings and Diagnostics. Its outputs belong to
the controller's external private problems folder: a diagnostic mark by default,
or an explicitly consented copy of up to 30 seconds of existing RAM audio. This
does not activate capture or playback. The UI calls `mark_problem(save_audio=…)`;
the backend controls availability, pinning, size and path reporting. Saving audio
is never implicit in opening the screen or marking without audio.

Screenshot-only generation additionally needs Pillow. The existing Anaconda
interpreter on this desktop has it; the isolated model environment does not.
No package installation is required for either normal application or UI tests.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -B -m prototype.tests.test_ui --screenshots prototype/tests/evidence/ui_stub_v1
```

```bat
"C:\Users\amiri\anaconda3\python.exe" -B -m prototype.tests.test_ui --screenshots prototype\tests\evidence\ui_stub_v1
```

Outputs are six PNGs and `UI_STUB_EVIDENCE.json` in the specified directory.
All screenshot captions, people and enrollment values are synthetic and labeled
STUB. This is frontend evidence only. The measured desktop client was 480×800
physical pixels, 96 DPI, per-monitor awareness 2. All six screens were visually
inspected. Initial testing found and fixed a caption area's geometry priority
that squeezed the Back to live controls. Updated tests passed afterwards.

## Presentation contract and remaining human checks

Snapshots own stable row IDs. The frontend edits existing Tk text ranges instead
of appending replacement rows. While browsing older text it restores the visible
row/character anchor; Back to live explicitly resumes following. Display retention
is controlled by the backend, so a retired row cannot remain an eternal anchor.

`provisional_case` always accepts the entire current raw utterance. It never
corrects words or inserts punctuation, never maintains an incremental token
buffer and never mutates raw text. Supplied final punctuated text takes precedence
when the row is final. Known spellings and explicit acronyms are limited hints,
not a language model or a promise that every proper noun will be correct.

The enrollment paragraph is an editable reading guide, never an expected ASR
answer. 15/30/60 seconds are unique usable-speech goals. Recording continues until
Stop (backend maximum 180 seconds); Read more gives guidance only. Save follows
the backend's `can_save`, never the elapsed-time progress bar.

The user was unavailable for live reading. Consent, real-room live captions,
personal reference capture/save/restart, different held-out speech, wrong-person
and Unknown behavior, and physical touchscreen comfort remain human-pending.
These stub screenshots and automated controls do not claim those checks passed.
CM5/touchscreen execution also remains hardware-pending. Native saved-file and
long-run evidence is maintained separately by the integration owner.

## Short native saved-file UI integration

`tests/native_ui_check.py` is an explicit real-controller/native-model check,
separate from unittest discovery. It consumes one prepared O0 mono16k file at
source pace, opens the actual portrait window, checks displayed row IDs/text,
visits Mode/People/Settings, then requests asynchronous close and waits for worker
closure. It never requests microphone input or enrollment. On this Windows host,
PowerShell/System.Drawing saves two genuine client screenshots without installing
Pillow in the inference environment. Screenshot capture itself is a diagnostic
pause and is not used as a UI latency measurement.

PowerShell from repository root:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tests\native_ui_check.py --wav 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav' --data-root 'G:\Just_Peachy_PROTO1\tests\ui_native_v1' --mode anonymous_conversation --recipe balanced
```

CMD/Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tests\native_ui_check.py --wav "G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav" --data-root "G:\Just_Peachy_PROTO1\tests\ui_native_v1" --mode anonymous_conversation --recipe balanced
```

Inputs: explicit prepared file, model directory (defaults to the documented
external models; override with `--models`), recipe/mode and a fresh external data
root. It refuses to overwrite an existing result. Use a new root for another run.
Outputs: `NATIVE_UI_RESULT.json`, `ui_evidence/01_native_partial.png`,
`ui_evidence/02_native_final.png`, and the controller's normal bounded session
journals. The JSON keeps actual row revisions, labels, displayed text, client
metrics, page reachability, source hashes observed at completion and worker-close
outcome. It is saved-file evidence, never live or personal-enrollment evidence.

The actual `ui_native_v1` run passed in 47.73 seconds: 480×800 physical client,
96 DPI, per-monitor awareness 2; three final displayed rows equal to the backend,
91 observed revisions across six transient segment IDs; real Unknown/anonymous
labels; one ASR and one speaker-model load. Mode, People and Settings were
reachable; the controller closed and its worker exited. Default output endpoints
were unchanged in five observations. Both native screenshots were visually read.
Result SHA-256: `2c83205b001db671d252309e5a6b2a747e5f482a7312c2872d33d5777789e02c`.
The later UI-only status-line change adds current recipe/tap; the test helper also
refreshes that status immediately before screenshots. Those changes do not alter
the accepted inference run and receive the focused stub check separately.
