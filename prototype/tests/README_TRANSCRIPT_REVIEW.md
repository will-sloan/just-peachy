# Task12 review contracts

Purpose: finite candidate preservation, protected meanings/nonwords/names,
prompt-like strings, strict choice parsing, cancel/timeout/memory pressure,
stale audio/session/annotation rejection, explicit adoption/Undo/export, model
provenance and 480×800 touch widgets. Inputs are disclosed synthetic waveforms,
decoder doubles and temporary local archives. No microphone or accuracy claim.

PowerShell from repository root:

```powershell
& .\.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p 'test_transcript_review*.py' -v
& .\.edge-speech-env\python.exe prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_12/unit_fresh
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p "test_transcript_review*.py" -v
.edge-speech-env\python.exe prototype\tools\run_unit_checks.py --output-dir Resumes\.uiiter2_12\unit_fresh
```

Outputs: unittest text or full-suite JSON/text/source-hash receipts in the fresh
chosen folder. Tests never use production profiles. Real-model checks and actual
controller screen captures are documented in ../tools/README_TRANSCRIPT_REVIEW.md.
