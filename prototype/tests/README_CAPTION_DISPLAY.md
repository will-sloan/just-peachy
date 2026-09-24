# Task 02 presentation checks

`test_caption_display.py` uses synthetic rows and a real Tk window. It checks
bounded pending/name transitions, unavailable versus collecting, preserved
numbered labels, same-turn grouping, immutable raw rows, stable marks during
native segment replacement, fixed smoothing deadlines, both client sizes,
long paragraphs/names, page extents, navigation and asynchronous close.
`test_ui.py` retains the existing enrollment keyboard/consent and spatial checks.
These checks open no microphone, personal gallery, models or USB control owner.

From the repository root in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_caption_display.py' -v
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_ui.py' -v
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B -m unittest discover -s prototype\tests -p "test_caption_display.py" -v
.edge-speech-env\python.exe -B -m unittest discover -s prototype\tests -p "test_ui.py" -v
```

Inputs are declared synthetic fixtures; outputs are unittest pass/fail results.
Measured timer latency and native saved-file screenshots are separate checks;
see `../docs/UIITER2_02_HANDOFF.md`. No mock check establishes identity accuracy,
WER improvement, microphone usability, physical touch comfort or CM5 performance.
