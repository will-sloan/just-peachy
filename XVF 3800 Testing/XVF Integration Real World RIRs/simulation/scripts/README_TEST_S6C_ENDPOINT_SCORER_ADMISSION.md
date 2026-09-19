# Final240-label admission through the unchanged V3 core scorer

Purpose: verify that the existing explicit additive registry contract accepts final C195/C196 while preserving all238 previous definitions and every metric source byte. This is an admission check, not a new scorer version. It checks the actual V7 profiles against C065/C079, only ID and XVF endpoint routing changed, no-gallery scope, exact amendment hashes, duplicate/parent/count/tamper rejection and the existing24 core fixtures.

Inputs: V7 registry, original registered design/calibration/rescue definitions, common-roster, fresh-followup, cadence and endpoint amendments. Output: a fresh independent_review/ENDPOINT_SCORER_ADMISSION_V1.json with complete source bindings and exact command arguments. No predictions, native models, hardware or scoring run. Earlier V3 code/results remain unchanged.

## PowerShell

~~~powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py "$sim\scripts\test_s6c_endpoint_scorer_admission.py"
~~~

## Anaconda Prompt / Command Prompt

~~~bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" "%SIM%\scripts\test_s6c_endpoint_scorer_admission.py"
~~~

Once the actual endpoint prediction index completes, use the unchanged s6c_analysis_v3.py with all four explicitly bound --registry-extension entries listed in the admission receipt and --expected-candidates240. Supply a fresh output subdirectory and --require-complete. The parent's completed-index notice determines the exact --index path; this check does not fabricate one. No dedicated naming extension is needed because these two profiles have no gallery. Full-profile-and-cue native dependencies still require actual endpoint-enabled ASR; scorer admission does not authorize substitution of old N01 words.

