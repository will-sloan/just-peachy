# Two reviewed Windows engineering previews

Purpose: give the user individually named launchers for the repaired source
with A0 Sherpa ASR or A2 Nemotron English ASR, both paired with D1 Nemotron 3
diarization and E0 ReDimNet. These are workstation-specific saved-file previews,
not portable Pi packages or accepted N4/N5 releases. Both have independently
reviewed one-file render/save/reopen/delete evidence on the same source.

The current entry point requires the independently reviewed e0-runtime-v1
derivative and E0-only configuration for the selected composition; missing
review evidence refuses launch. TitaNet fields/files are not required by the
selected application. Shadow instrumentation belongs only to its test harness
and is not enabled in the user preview. Earlier entry-point source is preserved
privately under preview-before-e0-v1.

Inputs: retained private source/runtime/assets and review receipts, and optionally
an already-prepared mono16k PCM16 O0 WAV. Default launch opens idle in anonymous
conversation mode, retaining E0 without claiming calibrated personal names.
Outputs: GUI captions and isolated saved sessions under
local/n5/prepi-20260928/Windows-A0-preview or Windows-A2-preview. Production
profiles are not used. Live capture and default audio-device observation are
disabled; no playback or enrollment is part of this workflow.

Only the user should launch a visible preview. Wait for numerical work to end;
actual launch refuses an active campaign owner, and one OS-held preview lock
prevents these two previews running concurrently. The application uses CPUs4/14,
one native thread per model and GPU off. Close it before further campaign runs.
There is no automatic fallback to a different backend when loading fails.

PowerShell from this directory:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
# Read-only checks; these do not open a GUI or model/device:
& $prePiPython -B start_preview_v1.py --backend A0 --check-only
& $prePiPython -B start_preview_v1.py --backend A2 --check-only
# Later user-operated visible launch, after workers finish:
& .\Start-SHERPA-NEMOTRON-REDIMNET.cmd
# Or, after closing it:
& .\Start-NEMOTRON-NEMOTRON-REDIMNET.cmd
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B start_preview_v1.py --backend A0 --check-only
"%PREPI_PY%" -B start_preview_v1.py --backend A2 --check-only
rem Later user-operated launch:
Start-SHERPA-NEMOTRON-REDIMNET.cmd
rem Or the other launcher after closing the first:
Start-NEMOTRON-NEMOTRON-REDIMNET.cmd
```

An optional `--wav "ABSOLUTE_PREPARED_O0_PATH.wav"` starts that saved file after
launch. No extra gain, mixing, synthesis or hardware input is introduced.
The agent only runs `--check-only`; private-desktop lifecycle evidence is
separate from verifying these new user launch commands.
