# Session reference contracts

Purpose: exercise contamination, duplicate/disjoint support, domain/freeze gates,
original-score baseline, caps, atomic disk failure, promotion/import/rename/delete,
restart and Undo, plus the actual portrait controls. Inputs: synthetic vectors,
waveforms and widget controller stubs. Outputs: unittest results. Personal data
is isolated in OS temporary directories. These are not accuracy experiments.

PowerShell from the repository:

```powershell
& .\.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p 'test_adaptation*.py' -v
```

Command Prompt / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p "test_adaptation*.py" -v
```

Full existing regression suite: use the same Python with
`prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_11/unit_fresh`.
Choose a fresh output folder. Native real-model coverage has its own README in
../tools/README_ADAPTATION.md; no unit result establishes a voice-accuracy gain.
