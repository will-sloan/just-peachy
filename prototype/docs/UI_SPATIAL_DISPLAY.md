# Live spatial display and mode selector

This README covers the compact portrait display in `app/ui.py` and the
`config/ui.json` preference. It uses controller telemetry and existing pipeline
associations; it performs no audio inference or beam steering. The same Tk code
runs on Windows and the CM5 export.

## Run and use

From the repository root in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

From CMD or Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

On the configured Raspberry Pi, from the exported release directory:

```sh
python3 main.py gui
```

Use **Mode** to choose the existing five modes or either new experimental spatial
mode. The controller keeps the compatible Balanced/Patient/Classic recipes and
O0/O1 audio choices. Spatial mode selection can select a compatible recipe when
the current recipe is incompatible; see the current mode guide and selector.

Enable **Settings → Live spatial display** to show a 125-pixel panel above the
transcript at the exact 480×800 size. This preference persists. It defaults off.
Hiding the panel changes display only, not the active pipeline mode. The separate
**Beam angles · live diagnostics** screen remains available.

After moving the tablet, use **Reset positions · tablet moved**. The controller
clears remembered locations and starts a fresh processing epoch while preserving
saved people. This is a manual action; no IMU motion detection is claimed.

## Read the panel

- Colors identify hardware outputs, not people. The selected fresh output has a
  thicker arrow and a named output/angle readout.
- Solid arrows are fresh readbacks. The speaking badge additionally requires
  fresh selected-direction speech evidence. Energy is shown in device units,
  not calibrated sound pressure. Music and other sounds can affect beams.
- A pipeline-associated speaker/name can appear beside an angle. Filled dots
  and “speaking” require fresh speaking evidence. Dashed arrows, hollow dots and
  “last known” mean a remembered position; they do not assert current speech.
- No name is inferred from an angle or a beam label. An association is an
  experimental pipeline decision and may be wrong. Two beams do not imply two
  people. At most two recent associations appear in the compact panel; the full
  transcript and diagnostics remain available.
- 0° is the MIC3 end, 180° the MIC0 end, relative to the board. The 90° direction
  folds front/rear together; it does not prove the physical side of the board.
  Telemetry ages are host receipt ages, not verified DSP estimate ages.

The mode selector uses **✓ simulation-supported** and **◇ experimental / real-world
validation needed**. Support describes the configuration and the tested conditions,
not field accuracy or every person, recipe and tap combination. Missing metadata
defaults to experimental. Experimental markers do not disable selection.

## Inputs and outputs

Inputs are the existing controller snapshot, `mode_metadata` and `spatial_view`.
The latter supplies `state`, `arrows`, `associations`, `stale_after_seconds`,
`speech` and raw `energy`. Arrows use known hardware IDs, `angle_deg`, `age_sec`,
`fresh` and `selected`. Only `associations` may supply person labels, with
`label`, `angle_deg`, `age_sec`, `fresh` and `speaking`. Invalid angles/ages are
ignored. Even if a backend flag is incorrect, the frontend requires RUNNING and
an age within the supplied freshness timeout for a current direction. Position
memories older than 12 seconds are hidden. Backend policy can expire them earlier.

Output is a bounded canvas and ordinary controller commands. Repainting is capped
at four updates per second and skipped when the visible state is unchanged.
Display changes persist through `settings_update({"spatial_visualization": bool})`.
Reset invokes `reset_spatial()`. Opening this display never starts a microphone,
loads an additional model, records audio or updates personal enrollment profiles.

## Focused verification

From the repository root, PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B -m unittest prototype.tests.test_ui -v
& 'C:\Users\amiri\anaconda3\python.exe' -B -m prototype.tests.test_ui --screenshots prototype/tests/evidence/ui_spatial_v1
```

CMD or Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B -m unittest prototype.tests.test_ui -v
"C:\Users\amiri\anaconda3\python.exe" -B -m prototype.tests.test_ui --screenshots prototype\tests\evidence\ui_spatial_v1
```

Tests use a synthetic controller without audio, models or personal data. They
exercise all seven mode selectors, legend metadata, compact height/caption room,
persisted toggling, reset dispatch, fresh/stale/expired positions and the separation
of hardware labels from person associations. Screenshot outputs are synthetic PNGs
and `UI_STUB_EVIDENCE.json`; they are frontend evidence, not real-world validation.
See `UI_ITERATION.md` for the established portrait, consent, enrollment, touch and
accessibility workflow.
