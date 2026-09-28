# Aggregate pre-Pi evidence

Purpose: produce a small reviewable receipt after all eight explicitly named
one-file/restart/shadow/E0-runtime Windows runs have independent passing reviews.
Inputs: private review, admission, source and terminal/phase/lifetime receipts.
Outputs: a fresh aggregate JSON with hashes, sample counts, model-use counters,
session wall time, proposed shadow fractions and three preserved model-free test
logs (4 shutdown regressions, 10 existing lifecycle tests, 6 E0 dependency tests).
The log counts are checked separately from the eight actual application runs.
No transcripts, PCM, model
weights, personal profiles or detailed speaker traces are copied into it.

The generator refuses missing/failed reviews, changed bindings and active exact
owners. It does not rerun models or replace the independent source reviewers.
Eight checks reuse one saved synthetic file; they are not eight independent
audio scenes, a full bank, a real-time claim or N4/N5 acceptance. Keep every
scope/limitation field with the summary when quoting results.

PowerShell from this directory, only after all required reviews exist:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $prePiPython -B summarize_checks_v1.py --output .\CHECK_SUMMARY_V1.json
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B summarize_checks_v1.py --output CHECK_SUMMARY_V1.json
```

Existing summaries cannot be overwritten. Read STATUS.md for later attempts.
