# S6C native timing diagnosis

Purpose: inspect one already completed, outcome-selected C105 / S45_08_07 / O0 ASR + O0 identity native/cache pair. It identifies the first transcript assignment difference, compares exact neural content and observation IDs, records relevant actual native log ordering, and reports the mature-evidence/ASR availability crossing. It does not execute models, modify profiles, replay policies, or rescore outputs.

Inputs: the SHA-pinned `gallery_native_integration_review_v1/RESULT.json`, its exact prediction/native receipt chains, evidence JSON, vector bytes and two existing native event logs; the C088 matched-parent prediction; frozen epoch2 scheduler source. Bytes are checked against the existing receipt declarations before parsing. The source diagnosis reads about 20 MB, not the full campaign. Only named measured timing fields are removed for neural-content comparison. UTC emission, source cursor and modeled availability remain distinct. Cached upstream native C065 events are frontend/order evidence; matched C105 policy decisions come from its cached C105 prediction.

Output: new `reports/S6C/20260910T123540Z/native_timing_diagnosis_v1/RESULT.json`, with exact source/helper bindings, field-level counts, first semantic transcript difference, selected log line numbers and clock values, and a scoped prospective sentinel. Existing output causes failure; preserve it and change namespace prospectively for another version. Six pure checks require no data or inference.

PowerShell:
```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
Set-Location -LiteralPath $sim
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' scripts/s6c_native_timing_diagnosis.py --self-test
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' scripts/s6c_native_timing_diagnosis.py
```

Anaconda Prompt / Windows CMD:
```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" scripts\s6c_native_timing_diagnosis.py --self-test
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" scripts\s6c_native_timing_diagnosis.py
```

No environment installation is needed. The script uses standard-library code and the already reviewed metadata reader. Run outside a quiet paced measurement interval. Equality of neural content does not prove equality of all numeric policy state; cue ages/reliability can differ. A release-order crossing explains the observed scheduler path, but this observational comparison does not identify the machine-level cause of compute-duration variation or establish general timing reliability.
