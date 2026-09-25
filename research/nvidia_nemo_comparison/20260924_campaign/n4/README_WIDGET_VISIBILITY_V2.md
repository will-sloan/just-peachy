# Private viewport test import-path repair

Purpose: `test_widget_visibility_v2.py` adds its exact script directory to the
private child's import path before using existing immutable evaluator readers.
V1's six widget regressions passed, but its saved-output test failed because
the package-launched child could not import the reader's script-local `common`.
The V1 source, admission and FAILED_PRESERVED result remain unchanged. No app,
viewport algorithm, caption, scene, inference or scoring behavior changed.

`probe_widget_visibility_v2.py` launches that derivative and binds its own code
and this README. Inputs, outputs, all seven tests, 160 saved-output cases,
CPU14/private-desktop isolation and resource limits are described in
README_WIDGET_VISIBILITY.md. The output must be fresh. This renders existing
modeled Controller results; it does not run models, saved audio or microphones,
control the user's desktop, or qualify source-paced latency or N4 acceptance.

PowerShell from the campaign worktree:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_widget_visibility_v2.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\widget-visibility-v2'
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_widget_visibility_v2.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\widget-visibility-v2"
```

Inspect RESULT.json, tests.json, isolation.json and the saved observation receipts.
ADMISSION.json binds exact source, inputs and code. Failed output is preserved;
do not rerun into it or edit its bound source. Only use the private launcher, never
invoke the Tk test module on the user's input desktop.
