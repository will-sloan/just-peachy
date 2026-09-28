# Error visibility repair

Purpose: preserve actual controller errors ahead of temporary informational notices in the shared Tk header. The real controls test found that invalid runtime selection correctly set ERROR without inference or fallback, but the GUI displayed "Backend selection queued. Start is explicit." indefinitely. The derivative changes one expression in `app/ui.py`; a controller error now takes priority over that notice. Existing source, models, profiles, tests and the failed attempt remain immutable.

Inputs: the hash-verified E0-only derivative, the failed actual private-desktop test, exact closed owner identities, and the extension window/storage census. Output: private `local/n5/research-extension-20260928/derivatives/ui-error-v1/prototype`, source/hash receipt and census. No capture, playback, target connection, model download or model inference occurs in the builder. It refuses existing outputs.

PowerShell / Anaconda PowerShell, from the campaign `n5/extension_20260928` directory:

```powershell
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_ui_error_v1.py
& $researchPython -B build_controls_v2.py
& $researchPython -B prepare_controls_v2.py --name a0-controls-v2 --backend nemotron_hybrid
# Only after terminal result and owner closure:
& $researchPython -B review_controls_v2.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v2' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v2-REVIEW.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_ui_error_v1.py
"%RESEARCH_PY%" -B build_controls_v2.py
"%RESEARCH_PY%" -B prepare_controls_v2.py --name a0-controls-v2 --backend nemotron_hybrid
"%RESEARCH_PY%" -B review_controls_v2.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v2" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v2-REVIEW.json"
```

Controls V2 retains the V1 assertions and bounds, changes the source binding to the new GUI derivative, and adds ancestry verification. Use A2 only after closed independent A0 review, with fresh name `a2-controls-v2` and backend `nemotron_600m`. This fixes an observed presentation defect; it does not change acoustic inference or establish full mode/N4/N5/CM5 acceptance. The test plan and fault/recovery protocol are in README_CONTROLS_V1.md.
