# Task 06 focused enrollment checks

Purpose: `test_paragraph_enrollment.py` checks timed/Done gates, negative audio,
source-support idempotence, unchanged math with deterministic model doubles,
ASR skips/failure/finalization, persistence/export/import, O0/O1 isolation,
collection cleanup and stop states. `test_paragraph_ui.py` drives actual Tk with
an explicit stub controller: touch selection, paragraph metadata, backlog,
animation bounds, Save gating and 480×800 client dimensions. Existing cleanup,
people, lifecycle and UI regressions still run in the complete suite.

From the repository root in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_paragraph*.py' -v
& .\.edge-speech-env\python.exe -B prototype/tests/test_paragraph_ui.py --screenshots Resumes/.uiiter2_06/ui_new
& .\.edge-speech-env\python.exe -B prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_06/unit_new
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p "test_paragraph*.py" -v
.edge-speech-env\python.exe -B prototype/tests/test_paragraph_ui.py --screenshots Resumes/.uiiter2_06/ui_new
.edge-speech-env\python.exe -B prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_06/unit_new
```

Inputs are deterministic arrays, model doubles, temporary stores and stub UI
data, never microphone input. Outputs: unittest results, optional fixture PNGs
and UI_SCOPE.json, or the full runner's source-bound JSON/log. Screenshot output
must be a fresh directory. Do not run competing UI tests during screenshot
capture. These are software/visual checks, not human enrollment or CM5 proof.
Actual model parity has its own small check in `../tools/README_ENROLLMENT.md`.
