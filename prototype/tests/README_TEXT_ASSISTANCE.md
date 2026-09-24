# Task 07 software and touch checks

Purpose: `test_text_assistance.py` tests off/review/approved-context behavior,
Amir/Emir ambiguity, real other names, titles, punctuation/case, substrings,
protected text, conflicts, profile rename/delete, restart, source-linked journal
recovery, separate manual correction/undo and export. `test_text_assistance_ui.py`
uses actual Tk with a stub controller to check touch vocabulary approval,
switches, unavailable bias, assisted markers and unchanged raw/identity layers.

PowerShell from repository root:

```powershell
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_text_assistance*.py' -v
& .\.edge-speech-env\python.exe -B prototype/tests/test_text_assistance_ui.py --screenshots Resumes/.uiiter2_07/ui_new
& .\.edge-speech-env\python.exe -B prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_07/unit_new
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p "test_text_assistance*.py" -v
.edge-speech-env\python.exe -B prototype/tests/test_text_assistance_ui.py --screenshots Resumes/.uiiter2_07/ui_new
.edge-speech-env\python.exe -B prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_07/unit_new
```

Inputs: original synthetic text, temporary preferences/archive, stub UI state.
Outputs: test results, optional fixture PNGs/JSON, full-suite source-bound receipt.
Use fresh evidence directories. No microphone, audible playback, neural model,
production personal store or acoustic-accuracy test runs here. UI screenshots
must run separately from other Tk tests. See the tools README for native audio.
