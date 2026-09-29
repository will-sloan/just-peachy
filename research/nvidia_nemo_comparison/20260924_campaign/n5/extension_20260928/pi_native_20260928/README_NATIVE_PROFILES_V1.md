# Prepared whole native streaming and delayed recipes

Purpose: make two pinned native geometry candidates selectable in an isolated adapter. This preparation is not an inference result or a release. Read NATIVE_GEOMETRY_FINDINGS_V1.md. `native_v3_streaming` uses chunk/right/left/FIFO/cache/refresh13/1/0/80/264/40. `native_v3_delayed` uses264/1/1/0/264/188. Counts are80ms coarse frames; output remains10ms. Every field is explicit. Original profiles, state ordering, runtime hash checks, sample mapping and C ABI stay unchanged.

The delayed profile still uses one ordered stateful native stream. It postpones speaker evidence by roughly a21-second center chunk plus context/compute; captions must remain independent and labels Pending/Unknown. It is not a second diarizer or silence gate. Smaller streaming FIFO/cache refresh may affect returning speakers; preserve these as real-world validation candidates until tested. Different geometry is not expected to reproduce current profile probabilities. Same-geometry generic/optimized and repeat1e-5 gates remain unchanged.

Inputs: exact parent adapter SHA d067f94ab2f64d536334ca31ee87a8243efd35d17f3895f66b9621fd0e09d7bd and a new output directory. Outputs: standalone derivative adapter and DERIVATIVE.json. No models, capture, playback, training, downloads or inference run. Future tests must bind a fresh native admission, unchanged model/runtime and source, check actual C-ABI values, frames/time/EOF/reset/repeat and process closure, then real processing/RSS/backlog/drain. Saved audio supports passage/resources only, not new WER/ASR quality metrics. Do not install this into active/preserved source or the current Pi app.

## PowerShell / Anaconda PowerShell

From this directory:

```powershell
& C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B prepare_native_profiles_v1.py --parent G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\derivatives\panel-journal-v1\prototype\vendor\edge_speech_pipeline\nemotron_diarization.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\native-profiles-v1
```

## CMD / Anaconda Prompt / Linux

For CMD/Anaconda Prompt use `cd /d` to this directory, then omit `&` from the command. No activation/install. On Linux use Python3 with the same arguments and actual staged parent/output paths. Preparation refuses an existing output directory. Execution requires a separate reviewed harness/admission and available resources; neither profile is silently promoted into B01/B02 by this script. Freeze settings before later user-ready real speech, dense conversation, quiet/overlap/returning-speaker and endurance validation.
