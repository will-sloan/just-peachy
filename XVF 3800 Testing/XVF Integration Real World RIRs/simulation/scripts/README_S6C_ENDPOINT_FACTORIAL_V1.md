# Final tracking × endpoint-advice factorial

Purpose: register the last two labels C195/C196, preserving all238 earlier labels and every384 prior effective route. C195 is C065 plus `xvf.mode=endpoint_only`; C196 is C079 plus `xvf.mode=both`. Profile IDs change; C195's metadata cue condition becomes real aligned for endpoint delivery while its tracker remains cue-disabled. Every other numeric/audio/model/ASR/punctuation setting remains exact. Four final cells are C065 none, C079 tracking only, C195 endpoint only and C196 both. Fixed N12 endpoint timings do not test this direction-advice hook.

Inputs are SHA-pinned V6 registry, exact frozen epoch5 APP, original design/panel and canonical bank. The real frozen EndpointAdvisorV2 and ASR loop execute with synthetic observations/tiny audio and a stub decoder for model-free tests: positive advice, missing/invalid/stale/old-source/low-reliability/fold-invalid/reused or reordered packet, speech preventing silence advice, cooldown, burst breaker and recovery. The exact ASR loop verifies native+advice coincident signals create one reset, plus complete7-sample tail/drain. No neural models or hardware are called by registration.

Outputs: `EFFECTIVE_PROFILE_REGISTRY_V7.json` (196 executable candidates/388 routes plus44 historical labels =240 total), four exact profile JSONs, `design/ENDPOINT_ADVICE_FACTORIAL_V1.json`, and `endpoint_factorial_v1/FUNCTIONAL_CHECKS.json`. The later `jobs` step creates224 native jobs over the56 fixed cases and both taps. All11 strict-empty/music cases are already in that panel and are asserted. Existing artifacts are never overwritten.

Both children explicitly require **FULL_PROFILE_AND_CUES**. Frozen native job identity binds full profile, cue condition, telemetry and both audio routes. Frozen matrixV4's exogenous key also returns the full profile for endpoint_only/both, then requires exact original full policy/cue/gallery. Do not substitute existing N01 ASR words/observations based only on recipe_id; endpoint advice may change reset boundaries and lexical output. These jobs require fresh actual native sessions. The old generic profile compiler does not apply this extension's `xvf_override`; use this dedicated additive compiler.

PowerShell registration (no models):

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$report = Join-Path $sim 'reports\S6C\20260910T123540Z'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_endpoint_factorial_v1.py" register
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_freeze_v2.py" --epoch epoch6 --registry "$report\EFFECTIVE_PROFILE_REGISTRY_V7.json" --gallery-index "$report\RESEARCH_GALLERY_INDEX_V2.json" --extra-script s6c_fresh_followup_design.py --extra-script s6c_policy_matrix_v4.py --extra-script s6c_cadence_neighborhood_v1.py --extra-script s6c_endpoint_factorial_v1.py
```

After epoch6 and the separate V5 coordinator are source-bound/reviewed:

```powershell
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_endpoint_factorial_v1.py" jobs
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_orchestrator_scan_v5.py" prepare --epoch epoch6 --jobs "$report\jobs\epoch6\endpoint_advice_v1.json" --workers 4 --name epoch6_endpoint_advice_scan_v1
```

Anaconda Prompt / CMD (existing interpreter; no package installation):

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "REPORT=%SIM%\reports\S6C\20260910T123540Z"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_endpoint_factorial_v1.py" register
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_freeze_v2.py" --epoch epoch6 --registry "%REPORT%\EFFECTIVE_PROFILE_REGISTRY_V7.json" --gallery-index "%REPORT%\RESEARCH_GALLERY_INDEX_V2.json" --extra-script s6c_fresh_followup_design.py --extra-script s6c_policy_matrix_v4.py --extra-script s6c_cadence_neighborhood_v1.py --extra-script s6c_endpoint_factorial_v1.py
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_endpoint_factorial_v1.py" jobs
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_orchestrator_scan_v5.py" prepare --epoch epoch6 --jobs "%REPORT%\jobs\epoch6\endpoint_advice_v1.json" --workers 4 --name epoch6_endpoint_advice_scan_v1
```

Preparation does not launch. Root owns scheduling and later `run` authorization through the separate coordinator README. All prior epoch/app/native/common/model files remain unchanged.

The amendment predeclares a compact actual audit: advisor proposals/reasons, native-only/advice-only/coincident reset flags and actual resets; first/last/final raw words, per-utterance boundaries and deletion/insertion/substitution counts; first-display/first-final/latest attribution; full paired PCM and ASR tail/drain/finalization; all11 empty/music cases; incomplete target-only versus complete reference denominators; nested model/API/advisor/reset/full-dispatch costs and physical invocation/cache counts. Full-dispatch advice does not run again on the final short ASR tail. Positive synthetic reachability, advice coincident with a native endpoint, or a changed number of utterances is not proof of improvement. Actual telemetry may yield zero extra accepted advice, which must remain an observed result.
