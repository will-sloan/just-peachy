# Bounded live timing lifecycle check

`check_timing_lifecycle.py` requires explicit microphone consent. It uses a fresh
private data directory and the existing XVF configuration and shared models.
It checks six seconds of Balanced/O0 input, a live-boundary change to strong
spatial/O1 for six seconds, Stop, two immediate Start/Stop cycles, then one
6.0045625-second prerecorded O0 speech fixture with a partial final block. It
loads each model once, opens one input/device owner at a time, and never plays
audio, saves microphone audio, enrolls anyone or opens your personal gallery.
The user need not read a script; human caption accuracy is not measured here.

PowerShell from the repository, after closing any app that owns the XVF:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\check_timing_lifecycle.py --consent --config "$env:USERPROFILE\JustPeachy\data\live_config.json" --wav 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav' --output "$env:USERPROFILE\JustPeachy\checks\timing-01"
```

CMD/Anaconda Prompt: omit `&`, use double quotes, and replace `$env:USERPROFILE`
with `%USERPROFILE%`. Choose an unused output directory. Inputs are the existing
site JSON, existing PCM16 mono16k O0 WAV and model cache. Outputs are bounded
private timing/restoration/session receipts, a short local speech fixture and
`TIMING_LIFECYCLE_CHECK.json`, including CPU/wall time and observed process RSS.
Existing user sessions, profiles and Windows render defaults are not modified.
No time quota or long soak is imposed. Each wait is for input or clean completion;
functional deadlines detect stalled capture/drain and fail explicitly.
