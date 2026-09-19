# Compile common-roster enrollment duration controls

`s6c_common_roster_profiles.py` adds C141–C146 to the original 184 registered
labels. Both fixed rosters contain the same 14 eligible people and competitors
at 5, 15 and 30 seconds. It compiles the existing real v3 API with the original
N01 cue-off naming policy. No model runs, calibration fits or probe scores occur.

Inputs: immutable V3 registry, original design, completed common30 gallery plan,
extension, template dependencies and original naming-analysis receipt. The helper
checks original authority bytes, exact six assignment keys, all 14-member gallery
manifests, and exact native parent-policy equality apart from the profile ID.
The independently reviewed gallery builder establishes same-person membership.

Outputs under `reports/S6C/20260910T123540Z`: a new duration amendment, twelve
effective profiles, `EFFECTIVE_PROFILE_REGISTRY_V4.json`, and additive
`RESEARCH_GALLERY_INDEX_V2.json`. All original index/registry files remain intact.
The new epoch must explicitly bind the additive index before running these IDs.
An old epoch cannot acquire these galleries by reading the new live registry.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:JP_S6C_SIM = $s6cSimulation
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s6cSimulation\scripts\s6c_common_roster_profiles.py"
```

Anaconda Prompt / CMD (use the installed interpreter; no activation/install):

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6C_SIM%\scripts\s6c_common_roster_profiles.py"
```

Exact reruns verify preserved registration/output contents. Changed inputs or
definitions require a new version and namespace. Rollback means select the old
V3 registry and original gallery index for a separate future epoch; do not delete
or replace either evidence lineage. No production or private gallery changes.

This amendment is outcome-informed by variable-roster results. Cohort selection
uses only E eligibility. All 240 scenes and all 777 probe occurrences remain;
there is no Common Voice duration effect claim for this CMU/HiFi-only cohort.
C143/C146 reuse the original 30-second runtime galleries, with explicit changed
intended-roster eligibility accounting. They are anchors, not new mathematics.
