# Just Peachy PROTO1

This opt-in application adapts the corrected S7 native speech pipeline into a
touch portrait application with explicit XVF microphone input and personal
voice enrollment. Historical S7 reports and galleries are unchanged. The
application opens idle; microphone use requires the visible Start/consent flow.

Read [START_PROTOTYPE.md](START_PROTOTYPE.md) for launch commands, external
data/model paths, and the remaining user-assisted live check. See `docs` for
mode, enrollment, UI and Raspberry Pi release/update instructions.

Version **0.1.4** adds selectable experimental Spatial-assisted/C079 and
Strongly spatial-assisted/C060 modes, plus the optional compact live spatial
display. See [the mode guide](MODE_GUIDE.md) and
[spatial adapter/run instructions](app/README_SPATIAL.md).
The Windows buffered-input fix from 0.1.3 is retained. Read
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
