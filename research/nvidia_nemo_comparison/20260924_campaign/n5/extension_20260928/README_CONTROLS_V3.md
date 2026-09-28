# Correct advanced-mode navigation in controls test

Purpose: the V2 actual-GUI test verified that the UI repair reveals the invalid-runtime error, then failed because the test looked for Numbered Unknowns (`anonymous_conversation`) on the ordinary Modes page. It is an explicit Advanced comparison mode. This was a test navigation error. The failed V2 remains preserved, with missing-model startup/recovery still unattempted.

V3 opens the actual Advanced page before invoking its actual Numbered Unknowns button. All assertions, inference/drain/time/resource limits, original saved source and the ui-error-v1 application derivative remain unchanged. Inputs/outputs and isolated startup fault protocol are those in README_CONTROLS_V1.md and README_UI_ERROR_V1.md. The builder records parent/child hashes, syntax-checks output and refuses existing generated files. It performs no inference or hardware access. No weaker test or application change is introduced to accommodate the misplaced test lookup.

PowerShell / Anaconda PowerShell, from this directory:

```powershell
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_controls_v3.py
& $researchPython -B prepare_controls_v3.py --name a0-controls-v3 --backend nemotron_hybrid
# After terminal result and exact owner closure:
& $researchPython -B review_controls_v3.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v3' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v3-REVIEW.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_controls_v3.py
"%RESEARCH_PY%" -B prepare_controls_v3.py --name a0-controls-v3 --backend nemotron_hybrid
"%RESEARCH_PY%" -B review_controls_v3.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v3" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-controls-v3-REVIEW.json"
```

After A0 closed independent review, A2 uses fresh name `a2-controls-v3` and backend `nemotron_600m`. No Pi, microphone, capture, playback or enrollment. A pass remains narrow Windows evidence and does not complete N4/N5 or qualify every mode.
