# Task 06 native audio parity check

`check_paragraph_enrollment.py` runs the pre-task quality class from the local
checkpoint ZIP and the updated timed/Done classes on identical prerecorded
audio. It compares exact vectors, source support, thresholds and inference call
counts. It checks ordinary unbiased ASR with the unrelated guide, actual profile
save/new-process restart/export/import, tap mismatch, duplicate source, short
audio, silence and clipping. No microphone or playback stream is opened.

From the repository root, PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B prototype/tools/check_paragraph_enrollment.py --wav Resumes/.uiiter2_04/native_v2/A_12s.wav --baseline-zip Resumes/.uiiter2_06/prototype_before_06.zip --output-dir Resumes/.uiiter2_06/native_new
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype/tools/check_paragraph_enrollment.py --wav Resumes/.uiiter2_04/native_v2/A_12s.wav --baseline-zip Resumes/.uiiter2_06/prototype_before_06.zip --output-dir Resumes/.uiiter2_06/native_new
```

Inputs: existing pinned models (optional `--models`), mono 16kHz prerecorded WAV
of 0.5–14s, trusted local before-06 ZIP. This helper executes that archived class;
do not supply an untrusted ZIP. The supplied genuine CMU fixture is from task04
and remains private. Use a fresh output directory; it refuses overwrite.

Outputs: NATIVE_ENROLLMENT_CHECK.json with exact asset hashes/runtime versions,
before/after vector delta, quality/read-estimate summaries, wall/CPU/peak-memory
measurements and code bindings. Private `people`, `imported` and export ZIP hold
fixture vectors and reference/ASR metadata, isolated from production data. No
vectors or transcript text are included in the compact JSON. A PASS establishes
bounded software/native execution, not field accuracy, human enrollment or CM5
resource qualification. No dataset sweep, neural tuning or installation occurs.
