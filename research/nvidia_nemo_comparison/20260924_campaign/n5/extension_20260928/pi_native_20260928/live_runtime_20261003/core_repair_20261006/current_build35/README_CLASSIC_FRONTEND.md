# Restored portrait frontend

`classic_frontend.py` restores the original Just Peachy caption layout and its
Start, Mode, People and Settings navigation. The single desktop shortcut opens
a scrollable backend-combination chooser. Choose Live microphone or Saved WAV,
then **OK** to open the familiar application idle. Start begins capture only
after consent and the current runtime's admission and model setup.

The retained `app.ui.PrototypeUI` source and its release manifest are verified
before loading the presentation graph. This GUI does not import the installed
controller, pipeline or model libraries. `ClassicController` translates the
current manager's worker state, indexed caption tail and spatial telemetry into
the original frontend API. All model/backend execution, 300-second ordinary
policy, separate ReDimNet/TitaNet galleries, BMI270/XVF handling, bounded disk
spooling, storage-capacity admission and worker closure remain in the current
runtime. Historical recording-slot managers and research dispatchers are not
used.

## Inputs and outputs

- Input: the current owned `Manager`, its verified deployment binding, retained
UI release, selected backend/embedding/source and the current recording store.
- Output: the rich portrait application; requests to the current worker manager;
  display-only preferences in `PORTRAIT_SETTINGS.json`; existing recording
  save/discard/export/delete receipts produced by the current storage subsystem.
- The main caption view displays up to 40 indexed rows and refreshes the database
  at most four times per second. History uses 25-row pages. No recording-count
  admission limit is introduced.
- Model initialization errors are displayed with the actual recorded failure.
  “Microphone never opened” describes the source state and is not treated as the
  underlying cause.

## Run on the Raspberry Pi

Use the reviewed **Just Peachy** desktop shortcut after the restored frontend
has been included in a new runtime package. The shortcut's owned launcher calls
`classic_frontend.show(manager)` (or
`ui_restore_20261004.classic_frontend.show(manager)` in a source checkout).
Do not run this module directly or point a shortcut at an old research script.

1. Choose the diarizer, embedding model and preset in the scrollable list.
2. Choose `live` or `saved`; press **OK · open application**.
3. Press Start. For Saved WAV, choose a mono PCM16 16 kHz replay file.
4. Stop waits for capture, processing/drain and worker closure.
5. Settings → Recordings shows completed sessions. Choose Save processed,
   qualified physical raw + processed, or Discard temporary audio after Stop.
6. Return to backend combinations changes the profile after owned workers close.
   Exit to desktop closes the frontend and current manager cleanly.

No automatic listening is enabled, and the frontend does not alter desktop
autostart configuration. Saved audio uses its recorded timeline; present sensor
motion does not change recorded directions. Existing voice galleries remain
model-specific. Enrollment, gallery editing and playback are explicitly
unavailable in this iteration.

## PowerShell, Command Prompt and Anaconda Prompt

These host commands run only the focused facade tests; they do not open the PC
display or contact the Pi. Set `RUNTIME` to the source checkout's
`live_runtime_20261003` directory. `OWNER` must name a new receipt in an existing
private preparation directory; do not reuse a closed receipt path.

PowerShell:

```powershell
$RUNTIME = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$OWNER = 'G:\path\to\fresh-private-preparation\CLASSIC_TEST_OWNER.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$RUNTIME\ui_restore_20261004\test_classic_frontend.py" --owner-receipt $OWNER
```

Command Prompt:

```bat
set "RUNTIME=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "OWNER=G:\path\to\fresh-private-preparation\CLASSIC_TEST_OWNER.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%RUNTIME%\ui_restore_20261004\test_classic_frontend.py" --owner-receipt "%OWNER%"
```

Anaconda Prompt uses the same `set` commands and explicit Python executable as
Command Prompt. No dependency installation or environment migration is needed.
The test coordinator sets CPU14 and registers its PID/create-time before project
imports. It checks consent/source separation, Stop/closure ordering, actual error
projection, bounded caption reads, post-Stop save, display-only preferences,
saved replay and separation of device display from anchor associations.

## Limitations

This source is a frontend repair, not a new inference/accuracy measurement.
Three imports used only by unsupported advanced pages are projected from the
verified originals into temporary in-memory helpers: enhancement route labels,
the script-review unavailable message, and seat tolerance/pure collisions. This
preserves the exact main `PrototypeUI` class and avoids importing NumPy or engine
packages merely to draw the interface. These helpers are removed after import
and cannot affect the separate model worker.
Native launch/capture, fullscreen rendering and touch use must be verified on the
new package. Live availability does not establish sustainable real time.
The old portrait UI's small recording-count retention controls are omitted;
current storage capacity and deliberate retention/deletion decisions apply.
Caption finality is only asserted when explicit `asr_final` provenance exists;
speaker stability is not treated as ASR finality.
