# Bounded native spatial integration check

`check_spatial_integration.py` runs the actual native ASR, segmentation, ReDimNet,
S6C tracker and S7 pipeline through both new spatial modes, sharing one resident
model bundle. It uses a 4–12 second contiguous copy of an existing mono16k PCM16
speech recording. This is a focused runtime check, not an optimization study.

The angles are an **explicit synthetic fixture**: a fixed 70° direction sampled
at 8 Hz, with delivery 10 ms after each declared source timestamp. The fixture
is independent of query timing, uses the file source's fixed epoch, never
refreshes old records during delayed computation, and only returns records
whose source support lies in the requested waveform window and whose delivery
has occurred. The original tracker freshness/reliability gates still apply.
No hardware is opened, no beam telemetry is represented as measured, and no
field performance or acoustic alignment is inferred from this check.

Inputs:

- `--wav`: existing already-gained mono16k PCM16 speech WAV; read-only.
- `--data-root`: **fresh** private output directory outside the application.
- `--models`: prepared shared model directory; defaults to normal shared assets.
- Optional `--start-sec` (default 0) and `--seconds` (default 12, allowed 4–12).

Outputs in the private root: exact contiguous PCM16 copy, normal native session
receipts, and `SPATIAL_INTEGRATION_CHECK.json` containing source/code hashes,
event/cue counts, completion states and model load counts. Personal profiles are
not read; the resolver receives an explicit empty gallery. Existing output
directories are rejected. The code never deletes or publishes these artifacts.

PowerShell, from the repository root:

```powershell
& '.\.edge-speech-env\python.exe' -B '.\prototype\tools\check_spatial_integration.py' --wav 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav' --data-root 'G:\Just_Peachy_PROTO1\checks\native_spatial_v1' --seconds 12
```

Command Prompt or Anaconda Prompt, from the repository root:

```bat
".edge-speech-env\python.exe" -B "prototype\tools\check_spatial_integration.py" --wav "G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav" --data-root "G:\Just_Peachy_PROTO1\checks\native_spatial_v1" --seconds 12
```

For export: activate the documented Python environment and run `python -B
tools/check_spatial_integration.py` from the prototype directory with your own
existing WAV and a fresh `--data-root`. No supplied path is a required platform
dependency. The script enforces at most 24 seconds of audio across two modes,
with a 90-second processing deadline per mode after native startup begins.

A pass requires both completed native sessions, actual source-window provider
calls, at least one qualified cue reaching each actual tracker, no fatal event,
and exactly one ASR load plus one speaker-model load across the two sessions.
Missing speech, slow computation or stale cues produce failure instead of
loosening thresholds. This check does not measure enrollment accuracy,
transcription quality, live USB timing, CM5 performance or real-person spatial
benefit. Use the existing prototype field guide for those real-world tests.
