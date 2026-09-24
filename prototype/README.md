# Just Peachy PROTO1

Task12 adds default-off Windows **audio transcript review** for explicitly selected
recorded utterances. Original captions remain immutable; adoption is a separate
user correction with Undo. No LLM was installed. See
[instructions](app/README_TRANSCRIPT_REVIEW.md) and [handoff](docs/UIITER2_12_HANDOFF.md).

Current local source also includes tasks10–11: optional noise routing and
default-off reversible session references. Open Settings → Advanced → Session
references / Undo. See [task11 run/data instructions](app/README_ADAPTATION.md)
and [handoff](docs/UIITER2_11_HANDOFF.md). Original enrollments stay unchanged;
the preserved task08 export does not contain these local extensions.

Local **task09 optional extension** adds default-off script-aware paragraph
evidence, a coverage/review page, and advisory base/alternate reference scores.
Original identity decisions remain unchanged; matched-content/phonetic scoring
is unavailable. See [controls and run instructions](app/README_SCRIPT_EVIDENCE.md)
and [handoff](docs/UIITER2_09_HANDOFF.md). The existing task08 ZIP below is
unchanged and does **not** include task09; use this local source to try it.

**Consolidated export: proto1-0.2.0 (UIITER2 tasks01–08).** Includes the accepted
timing, captions/touch, linked sessions, roster, seats, paragraph enrollment and
text-assistance changes below. Task08 adds motion-event safety and a checked
release/update workflow. Start with the [release quickstart](docs/CM5_RELEASE_QUICKSTART.md),
[handoff](docs/UIITER2_08_HANDOFF.md) and [wiring/arrival checklist](docs/CM5_WIRING_AND_BRINGUP.md).
Windows software/native-file checks are separate from pending CM5 hardware
qualification. Existing recipes, model hashes and private profiles are retained.

Local **UIITER2 task 07** adds **Settings → Text assistance / vocabulary**:
review-only spelling suggestions, explicitly approved contextual rules, raw-text
review and reversible manual correction history. Both switches default Off.
Enrolled-name acoustic bias is unavailable with the current tokenizer assets;
greedy ASR stays unchanged. See [run/use notes](app/README_TEXT_ASSISTANCE.md) and
[the handoff](docs/UIITER2_07_HANDOFF.md). Task08 now includes these changes in the export.

This opt-in application adapts the corrected S7 native speech pipeline into a
touch portrait application with explicit XVF microphone input and personal
voice enrollment. Historical S7 reports and galleries are unchanged. The
application opens idle; microphone use requires the visible Start/consent flow.

Read [START_PROTOTYPE.md](START_PROTOTYPE.md) for launch commands, external
data/model paths, and the remaining user-assisted live check. See `docs` for
mode, enrollment, UI and Raspberry Pi release/update instructions.

Local **UIITER2 task 06** adds **Read paragraph → Done**, limited-evidence status,
ordinary-ASR script estimates and honest animated enrollment progress while
preserving timed goals and audio embedding math. See the
[enrollment guide](docs/ENROLLMENT_GUIDE.md),
[implementation/run notes](app/README_ENROLLMENT.md) and
[task 06 handoff](docs/UIITER2_06_HANDOFF.md). This local source update does not
rebuild the historical 0.1.4 exports; human enrollment/CM5 checks remain pending.

Version **0.1.4** adds selectable experimental Spatial-assisted/C079 and
Strongly spatial-assisted/C060 modes, plus the optional compact live spatial
display. See [the mode guide](MODE_GUIDE.md) and
[spatial adapter/run instructions](app/README_SPATIAL.md).
The local **UIITER2 task 01** update further repairs live timing and Stop without
changing modes or model assets; read [its handoff](docs/UIITER2_01_HANDOFF.md).
Local **UIITER2 task 02** adds compact captions, bounded display smoothing and
pending identity, conditional recovery, touch navigation feedback and clearer
beam legends. Read [its handoff](docs/UIITER2_02_HANDOFF.md) and
[display run/check guide](app/README_CAPTION_DISPLAY.md).
Local **UIITER2 task 03** adds linked developer conversations, opt-in exact
float32 audio, indexed transcript/model windows, resource samples and isolated
explicit-output listening. Read [the workflow/run guide](app/README_SESSIONS.md)
and [the handoff](docs/UIITER2_03_HANDOFF.md).
Local **UIITER2 task 05** adds explicit experimental assigned-seat modes, a
touch layout editor, soft/strong hybrid prior and manual motion invalidation.
Read [the run guide](app/README_SEATS.md), [seat semantics](docs/SEAT_SEMANTICS.md)
and [the handoff](docs/UIITER2_05_HANDOFF.md). Templates are unanchored until Apply;
direction names are marked seat assumptions. Real-person and CM5 checks remain pending.
Local **UIITER2 task 04** adds actual UUID-selected galleries, explicit closed
group assumptions, constant-Unknown defaults and Advanced raw voice/spatial
scores. Read [mode semantics](docs/MODE_SEMANTICS.md),
[run/control instructions](app/README_ROSTER.md) and
[the handoff](docs/UIITER2_04_HANDOFF.md). Existing parent algorithms and default
thresholds are retained; display filtering is separate from identification.
The existing 0.1.4 export remains the historical package, not this uncommitted
iteration. The earlier Windows buffered-input fix is documented in
[Windows live fix and validation](docs/WINDOWS_LIVE_FIX.md) and
[Beam diagnostics](docs/BEAM_DIAGNOSTICS.md). Close and reopen an already-running
GUI to load the update. One source package serves Windows and Linux; Pi native
runtime/device bring-up remains pending.

## Development commands

From the repository directory in PowerShell:

```powershell
& .\.edge-speech-env\python.exe .\prototype\main.py validate
& .\.edge-speech-env\python.exe .\prototype\main.py gui
& .\.edge-speech-env\python.exe -m unittest discover -s .\prototype\tests -v
```

From CMD or Anaconda Prompt:

```bat
.edge-speech-env\python.exe prototype\main.py validate
.edge-speech-env\python.exe prototype\main.py gui
.edge-speech-env\python.exe -m unittest discover -s prototype\tests -v
```

Use the existing isolated interpreter above. No global package upgrade is
required. A relocated release accepts another compatible Python path through
`Start-Prototype.ps1 -Python`, or `JUST_PEACHY_PYTHON`.

## Inputs and outputs

Inputs are explicit consented XVF microphone samples or prepared mono16k PCM16
WAVs; the eight bound local models; and optionally the user's private UUID
profiles. Outputs are live partial/final captions, optional provisional speaker
labels, bounded session text/diagnostics and explicitly saved personal vectors.
Default personal data is `%USERPROFILE%\JustPeachy\data` on Windows, or
`~/JustPeachy/data` on Linux. Models are separate in the sibling
`shared/models/<sha256>/<filename>` directory. Override using `--data-root`,
`--models`, `JUST_PEACHY_DATA`, or `JUST_PEACHY_MODELS`.

No default playback device/volume setter, render stream, cloud service, research
gallery preloading or unattended enrollment is part of the application.

## Code map and lifecycle

`main.py` is the entry point. `app/controller.py` owns one active session and
serializes mode/gallery changes. `app/pipeline.py` uses the locally migrated
`vendor/edge_speech_pipeline` inference/scheduler/presentation algorithms.
`app/buffers.py` replaces ambient PCM spooling with a120-second RAM ring and
bounded asynchronous rotating field journals. Slow readers fail explicitly.
`app/people.py` stores UUID references using the same192D ReDimNet preprocessing
and conservative score/margin resolver. `app/live_audio.py` owns the input-only
XVF stream and project device lease. Each new recipe/source/gallery epoch starts
fresh temporal state; model weights are reused when compatible.

Session journals retain at most10 completed unpinned sessions/256MiB target.
Folders with `PINNED` are never automatically removed. Less than2GiB free stops
new capture. Personal profiles and source WAVs are not retention targets.
Live/reference samples are held in RAM and not saved as WAVs by default. Text
journals may contain sensitive speech; keep the private data directory private.
The experimental strict focus view can hide target speech; Show all restores
the complete retained transcript. Identity accuracy is not guaranteed.

`runtime.lock` exclusively owns a personal data directory for the app or release
activation. After an abnormal process crash, confirm the recorded PID is no
longer running and no release installer is active before manually removing
that exact lock. The app never guesses that another owner is stale.

## Testing scope

Meaningful tests cover source timing/gaps, bounded writer stalls, raw-text and
late-identity preservation, private enrollment persistence and safe import,
touch presentation and release activation/rollback. File/stub/live evidence is
labelled separately. CM5 hardware is unavailable and must not be inferred from
Windows or Linux static checks. See the final acceptance report for actual
results, limitations and source bindings.

## Optional noise routing (task10)

Settings → Advanced → Noise / model routing exposes Bypass (default), ASR, identity and both. One stateful DPDFNet baseline is experimental; results are mixed. See [runtime and run instructions](app/README_NOISE.md), [handoff](docs/UIITER2_10_HANDOFF.md) and [native checks](tools/README_NOISE.md). Current local source includes tasks09–10; task08 ZIP is preserved.
