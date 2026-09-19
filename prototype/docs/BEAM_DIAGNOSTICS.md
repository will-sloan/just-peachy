# Live beam diagnostics

The Windows and Linux prototype share the same beam display. Start a consented
live XVF input session, then open **Settings → Beam angles · live diagnostics**.
The page remains available while captions run. Opening this page alone never
opens a microphone, changes a device control, or starts a second capture.

Six colors identify hardware outputs: Focused 1, Focused 2, Scanning, AEC
auto-select, Processed output and Selected auto. The last two come from the audio
manager's selected-angle getter and use dashed arrows. These outputs can agree,
disagree, or follow music. Several arrows do not establish several speakers.
The display does not steer hardware beams.

Device replies are radians, converted to the native linear 0–180 degree scale.
0° points toward the MIC3 end and 180° toward MIC0. The sketch places MIC3 on the
right, MIC0 on the left, and 90° above the board. This is a folded board frame:
front/rear are ambiguous, and board orientation relative to the room still
matters. The arrow is not a verified physical 2D location.

Arrows show finite recent readbacks. NaN, invalid/out-of-range values and expired
fields are hidden. Each field has its own host receipt age, with a 2.5 second
display expiry. Host receipt does not establish when the DSP observed the sound;
repeated values are not independent fresh estimates. Angles and speech energies
are asynchronous. The display does not claim an atomic snapshot, identify a
person, use an angle to enroll a person, or alter ASR/identity decisions.

The live **Spatial-assisted** recipe remains unavailable: it needs a qualified
causal audio/telemetry association and validation beyond this diagnostic page.
Other recipes still receive the XVF's processed, beamformed audio; their software
identity and enrollment paths do not currently consume numerical directions.

## Inputs, outputs and lifecycle

`app/beam_diagnostics.py` takes a serialized, timeout-bounded read-only getter
supplied by the active live adapter. It reads only `AEC_AZIMUTH_VALUES`,
`AEC_SPENERGY_VALUES` and `AUDIO_MGR_SELECTED_AZIMUTHS`. Construction and snapshots
perform no device access. The live source starts the worker after microphone
consent and successful route verification, and joins it before restoring routing
or releasing ownership. A new live session gets a fresh worker and empty state.

The worker makes at most two getter calls per second in total, rotating through
the three fields. Each field therefore refreshes at most about every 1.5 seconds,
plus command time. It waits after each completed call and never catches up in a
burst. Diagnostic getters share the route-control lock, create no per-read command
receipt list and retain only three latest field arrays plus counters. A getter
failure disables diagnostics and hides arrows; it does not fail recognition.
Stop waits for the single bounded in-flight getter before owner cleanup.

Outputs are a constant-size snapshot under controller `beam_diagnostics`, counters,
read-only status/error text and the GUI sketch. No audio, speaker embeddings,
training artifacts or continuous research telemetry files are written by this
module. The desktop site configuration still supplies the matched host tool and
physical endpoint as described in [LIVE_AUDIO.md](LIVE_AUDIO.md). Linux needs its
matching native host tool and ALSA endpoint; the diagram itself is portable Tk.

## Run on this Windows desktop

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype'
.\Start-Prototype.cmd
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
Start-Prototype.cmd
```

Select Start, review the identified XVF device and grant microphone consent. Then
open Settings and Beam angles. Stop ends capture and diagnostic reads together.
On the prepared Pi installation, use its normal documented prototype launcher;
see [PI_DEPLOYMENT_WORKFLOW.md](PI_DEPLOYMENT_WORKFLOW.md).

## Verify without hardware

These tests inject synthetic getter replies and use a fake GUI controller. They
exercise parsing, fixed endpoints, independent expiry, constant-size snapshots,
read-rate limits, failure isolation, stop/join, and the live-accessible Tk page.
They never use a microphone, USB transport or neural model. GUI tests create
temporary test windows; fixtures are not hardware accuracy evidence.

PowerShell, from the repository root:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& '.\.edge-speech-env\python.exe' -B -m unittest discover -s prototype/tests -p test_beam_diagnostics.py -v
& '.\.edge-speech-env\python.exe' -B -m unittest prototype.tests.test_ui.UITests.test_beam_diagnostics_remain_accessible_live_and_hide_stale_arrows -v
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
".edge-speech-env\python.exe" -B -m unittest discover -s prototype/tests -p test_beam_diagnostics.py -v
".edge-speech-env\python.exe" -B -m unittest prototype.tests.test_ui.UITests.test_beam_diagnostics_remain_accessible_live_and_hide_stale_arrows -v
```

Portable environments use their installed compatible Python instead of the local
`.edge-speech-env` path, with the same repository-root working directory. Linux
Tk tests need a display server. Test console output is the only retained output.
