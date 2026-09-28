# Preconnection Windows choices

This is the separate pre-Pi development window authorized on September 28.
Read STATUS.md for current evidence and CHECK_SUMMARY_V1.json when present for
the independently reviewed aggregate. The earlier campaign's partial closure
and failed attempts remain preserved. These are engineering previews; N4/N5
and native Pi acceptance remain incomplete.

| User-operated launcher in this directory | Components |
| --- | --- |
| Start-SHERPA-NEMOTRON-REDIMNET.cmd | Existing Sherpa ASR + Nemotron 3 diarizer + ReDimNet |
| Start-NEMOTRON-NEMOTRON-REDIMNET.cmd | Nemotron English ASR + Nemotron 3 diarizer + ReDimNet |

Both use the same front end and revised Controller, keep ReDimNet, and require
independent passing evidence for the E0-only runtime before opening. They start
idle in anonymous conversation mode. Choose an already-prepared mono16k PCM16
saved O0/O1 file; use one preview at a time after campaign workers finish.
No microphone, playback or personal enrollment is enabled. These isolated
preview stores do not contain your personal profiles. Anonymous labels do not
establish persistent personal identity. No backend silently falls back.

Purpose: provide exact launch paths to the reviewed private source and assets
on this workstation. Inputs: retained runtime/model/source bindings and a saved
WAV chosen by the user. Outputs: displayed captions and isolated saved sessions
under local/n5/prepi-20260928/Windows-A0-preview or Windows-A2-preview. The source
includes the bounded shutdown repair and removes the retired TitaNet manifest
dependency from E0 selection. Runtime shadow logging is a test instrument and
is not enabled in these user previews.

PowerShell from this directory:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $prePiPython -B start_preview_v1.py --backend A0 --check-only
& $prePiPython -B start_preview_v1.py --backend A2 --check-only
# Later user-operated visible launch, after workers finish:
& .\Start-SHERPA-NEMOTRON-REDIMNET.cmd
# Or, after closing the first:
& .\Start-NEMOTRON-NEMOTRON-REDIMNET.cmd
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\prepi_20260928
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B start_preview_v1.py --backend A0 --check-only
"%PREPI_PY%" -B start_preview_v1.py --backend A2 --check-only
rem Later user-operated launch, only one at a time:
Start-SHERPA-NEMOTRON-REDIMNET.cmd
```

The agent runs only `--check-only`; actual automated GUI tests use a separate
private desktop and leave your input/focus available. See README_PREVIEW.md
for the optional saved-WAV command argument and exact constraints.

The preserved baseline Pi archive and later installation/storage checks are in
../PI_RECONNECT_QUICKSTART_V1.md. That baseline archive does not contain these
new Nemotron candidates. The actual ARM64 Python/Tk/speaker/punctuation/GUI
path, long native ASR conformance and native CPU/RAM/thermal/endurance behavior
remain to be verified. Do not treat short emulated checks as native Pi speed.
No Pi connection, OS change, audio capture or training has been performed.

The held experiment catalogue remains in ../realtime_validation_v1. Narrow
one-file shadow checks do not qualify applied silence removal or a parallel
optimization. This test file is about 66% exact digital zero; dense conversation,
quiet/short/overlap speech and returning speakers require independent held-out
validation. All actual inference here retained every source sample.
