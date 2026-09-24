# Task09 contract and portrait checks

Purpose: test optional paragraph evidence while protecting original enrollment,
identity, profile storage and the 480×800 interface. No microphone or playback.
`test_script_evidence.py` uses explicitly synthetic audio/models and temporary
stores. `test_script_evidence_ui.py` uses actual Tk widgets with disclosed fixture
snapshots; its screenshot mode loads copied genuine native profiles through the
actual controller. The comparison screenshot is frozen native evidence, not a
live-query or accuracy test. `check_native_people.py` also accepts optional
`alternate_advisory=True` for the task09 native harness; default behavior is unchanged.

From repository root, PowerShell:

```powershell
& .\.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p test_script_evidence.py -v
& .\.edge-speech-env\python.exe prototype/tests/test_script_evidence_ui.py -v
& .\.edge-speech-env\python.exe prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_09/unit_new
& .\.edge-speech-env\python.exe prototype/tests/test_script_evidence_ui.py --native-evidence Resumes/.uiiter2_09/native_accepted --screenshots Resumes/.uiiter2_09/ui_new
```

CMD / Anaconda Prompt: use the same commands without the leading `&`, for example:

```bat
.edge-speech-env\python.exe prototype/tests/test_script_evidence_ui.py -v
.edge-speech-env\python.exe prototype/tools/run_unit_checks.py --output-dir Resumes/.uiiter2_09/unit_new
```

Inputs: current app/runtime; for screenshots, a completed native evidence folder
from the tool README, and a **fresh** output directory. Outputs: unittest results;
the full runner writes source-bound JSON/text receipts. Screenshot mode writes
four PNGs, `UI_CHECK.json` and a private copied fixture store. Never point it at
production data. Screen checks require a Windows interactive desktop; do not run
other GUI tests concurrently. Full-suite runner explicitly collects Tk objects
on the main thread between tests to avoid Tcl destruction on later workers.

Coverage: correct/wrong/skipped/repeated scripts, partial decoder-tail timestamps,
endpoint offsets/indexing, no tiny/duplicate support, note/raw separation,
controller Done→analysis→Save, helper-failure fallback, actual JSON size bounds,
base-score parity, O0/O1 separation, export/import/rename/delete, tamper refusal,
feature downgrade refusal/lock cleanup, touch controls and 480×800 geometry.
Synthetic contracts alone do not complete task09; actual audio checks are separate.
