# Freeze an explicit additive execution epoch

`s6c_freeze_v2.py` creates a new immutable source/asset/profile/gallery manifest
for S6C. It accepts an explicit registry and gallery index, allowing additive
common-roster conditions while retaining every earlier epoch. It refuses any
application, model, interpreter or package drift from epoch2. It does not run
models or alter active code, the production GUI, canonical inputs or galleries.
The original epoch2 authority is SHA-pinned. All copied APP bytes are verified
after copying. The entire original epoch2 execution module is copied from its
bound snapshot, and worker common utilities retain their exact epoch2 bytes.
Existing-epoch admission rechecks the manifest digest, assets, environment,
actual APP inventory and exact worker module/common bytes. Input and scene
authorities must equal epoch2 before publication and on existing-epoch admission.

Inputs: completed effective registry with exact profile file bindings, completed
gallery assignments, original epoch2 model and source authority, local helper
sources, and current storage admission. Every additional script name must be a
plain local `.py` filename. Duplicate gallery keys and missing named conditions
fail before freezing. Native job validation still checks exact case assignment
and template dependencies before actual use.

Outputs: `staging/s6c/20260910T123540Z/<epoch>` frozen app/scripts/documentation,
and `reports/S6C/20260910T123540Z/<EPOCH>_EXECUTION_MANIFEST.json`. The manifest
includes all additive registration authorities and the exact gallery index.
An exact rerun verifies existing inputs/source bytes. A failed partial freeze
stays preserved; diagnose it and select a new epoch name.

PowerShell example (select the actual reviewed registry before execution):

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = "$s6cSimulation\reports\S6C\20260910T123540Z"
$env:JP_S6C_SIM = $s6cSimulation
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s6cSimulation\scripts\s6c_freeze_v2.py" --epoch epoch4 --registry "$s6cReport\EFFECTIVE_PROFILE_REGISTRY_V5.json" --gallery-index "$s6cReport\RESEARCH_GALLERY_INDEX_V2.json" --extra-script s6c_fresh_followup_design.py --extra-script s6c_policy_matrix_v4.py
```

Anaconda Prompt / CMD:

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%JP_S6C_SIM%\reports\S6C\20260910T123540Z"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6C_SIM%\scripts\s6c_freeze_v2.py" --epoch epoch4 --registry "%S6C_REPORT%\EFFECTIVE_PROFILE_REGISTRY_V5.json" --gallery-index "%S6C_REPORT%\RESEARCH_GALLERY_INDEX_V2.json" --extra-script s6c_fresh_followup_design.py --extra-script s6c_policy_matrix_v4.py
```

Add `--extra-script helper_name.py` for each reviewed future helper that must be
inside the source graph. The existing frozen runner and its unchanged native
worker execute this epoch's jobs; the separate matrix V4 can admit an earlier
epoch only after strict APP/model/environment/frontend dependency checks. A new
execution digest is recorded even when only orchestration/registry context grew.
Rollback selects a prior frozen epoch for future work; do not modify or delete
either source lineage or reuse an old epoch name for new definitions.
