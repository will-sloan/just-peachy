# S6C N07 cadence due-floor neighborhood V1

Purpose: register four outcome-informed neighbors after the completed336-cell native cadence audit. C191/C192 clone C071 cue-off/C082 real with voice_observation_floor_sec=.5; C193/C194 clone the same parents with2.0. Existing1.0 parents remain. Only executable profile_id and that embedding setting change. Recipe family stays N07, with FULL_PROFILE_AND_CUES dependence: these are448 new actual native panel jobs, not replay substitutions.

Inputs: exact V5 registry, original candidate definitions, bound cadence audit RESULT, and frozen epoch4 APP. Registration runs model-free functional tests through the actual EvidenceAdmissionV3 at .5/1/2, validates all eight new profiles using the real schema, and writes four definitions, eight JSON profiles, V6 registry (194 executable candidates/384 routes;238 total labels including44 preserved historical methods), and DUE_LEDGER_CHECKS.json. All original376 rows remain byte-equivalent JSON values. Existing destinations are never overwritten.

The field is a due-ledger threshold, not proof that a selected debtor spoke. An admitted global window acknowledges all due entries; other onset/cosine/cue triggers and sparse admission still execute. Rejected windows do not acknowledge debt. The dedicated compiler applies the explicit embedding_override to exact parent profiles; the old generic make_profile does not compile this extension. Native execution consumes the bound effective profile. No model/APP/ASR/tracker algorithm is changed.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $py "$sim\scripts\s6c_cadence_neighborhood_v1.py" register
& $py "$sim\scripts\s6c_freeze_v2.py" --epoch epoch5 --registry "$sim\reports\S6C\20260910T123540Z\EFFECTIVE_PROFILE_REGISTRY_V6.json" --gallery-index "$sim\reports\S6C\20260910T123540Z\RESEARCH_GALLERY_INDEX_V2.json" --extra-script s6c_fresh_followup_design.py --extra-script s6c_policy_matrix_v4.py --extra-script s6c_cadence_neighborhood_v1.py
& $py "$sim\scripts\s6c_cadence_neighborhood_v1.py" jobs
& $py "$sim\scripts\s6c_orchestrator_scan_v4.py" prepare --epoch epoch5 --jobs "$sim\reports\S6C\20260910T123540Z\jobs\epoch5\cadence_floor_v1.json" --workers 4 --name epoch5_cadence_floor_scan_v1
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
"%PY%" "%SIM%\scripts\s6c_cadence_neighborhood_v1.py" register
"%PY%" "%SIM%\scripts\s6c_freeze_v2.py" --epoch epoch5 --registry "%SIM%\reports\S6C\20260910T123540Z\EFFECTIVE_PROFILE_REGISTRY_V6.json" --gallery-index "%SIM%\reports\S6C\20260910T123540Z\RESEARCH_GALLERY_INDEX_V2.json" --extra-script s6c_fresh_followup_design.py --extra-script s6c_policy_matrix_v4.py --extra-script s6c_cadence_neighborhood_v1.py
"%PY%" "%SIM%\scripts\s6c_cadence_neighborhood_v1.py" jobs
"%PY%" "%SIM%\scripts\s6c_orchestrator_scan_v4.py" prepare --epoch epoch5 --jobs "%SIM%\reports\S6C\20260910T123540Z\jobs\epoch5\cadence_floor_v1.json" --workers 4 --name epoch5_cadence_floor_scan_v1
```

Run each preparation step once in order after independent review. The unchanged additive freezer copies exact original APP/whole native worker/common/assets/environment into a new namespace. `jobs` uses the separately SHA-pinned epoch5 V4 admission and unchanged native make_job/validate_job to prepare448 cells; it rehashes dependencies but does not construct models. The last command only prepares a coordinator admission. Root owns the later run queue; no native launch is part of these commands. Epoch5 can be frozen before the V4 wrapper is completed; `jobs` and coordinator preparation require its independently reviewed epoch5 pin.
