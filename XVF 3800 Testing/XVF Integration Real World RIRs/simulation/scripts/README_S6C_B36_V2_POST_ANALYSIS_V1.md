# B36 V2 post-analysis and normalization

Purpose: process the single, explicitly admitted B36 V2 historical paced batch using unchanged historical scientific conversion and runtime metadata formulas. This helper starts no models, native audio or hardware. It neither releases a lease nor substitutes an old G-drive archive for the V2 coordinator's explicit C-drive release proof.

Preparation and analysis privately reuse the held fast adapter's original code objects. Normalization privately reuses the original normalizer's run code and keeps its condition, tail, ownership, uniqueness and analysis-chain functions unchanged. Only source/module/reader contexts differ. No original module globals, controls recovery code, native worker or scientific scorer is edited.

The separate inventory facade must be held and independently reviewed before actual use. Source checks alone do not admit a completed batch.

## Inputs and outputs

Inputs are exact path/SHA pairs for the finite observer index and this fixed manifest:

`G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_fast_v2\MANIFEST.json`

SHA256: `a19d8b5bebdc425256f8f546072b018ff5c65665a23ffab3064e75fafe7294b1`.

The new schema is `s6c-historical-paced-b36-fast.v2`. The inventory must prove the exact original 40 B36 jobs, original worker/assets, completed native grid, owned process closure, successful actual observer outcome and the V2 coordinator's explicit C archive. A failed or incomplete chain cannot become a complete normalized row.

The fixed analysis namespace is `b36_v2_analysis_fast_v2`. The original adapter writes its exact request under `REPORT/fast_post_analysis_admission/historical/<namespace>/REQUEST.json` and the original historical converter writes `PLAN.json`, `RESULT.json`, per-cell measurements and separate repetition prediction indexes under `REPORT/historical_paced_analysis/<namespace>`.

Normalization takes the unchanged schema `s6c-runtime-normalization-inputs.v1`, status `EXPLICIT_FINITE_SCOPE`, the same observer index, the original exact `working_registration` binding, and exactly one request:

```json
{
  "input_id": "b36_v2_actual",
  "kind": "historical",
  "generation": "research",
  "manifest": {"path": "EXACT_MANIFEST_PATH", "bytes": 553498, "sha256": "a19d8b5bebdc425256f8f546072b018ff5c65665a23ffab3064e75fafe7294b1"},
  "analysis_receipt": {"path": "EXACT_COMPLETED_ORIGINAL_RESULT_PATH", "bytes": 0, "sha256": "REPLACE_WITH_ACTUAL_SHA"}
}
```

The example is a schema illustration, not executable evidence. Replace all bindings with their actual bytes/counts/hashes. `physical_inventories` must be empty or absent. Do not include `external_recovery`: B36 V2 performs its own verified archive. The completed result path must be the fixed analysis result above.

Normalization writes unchanged `RUNTIME_ROWS.json`, `PHYSICAL_ROWS.json` and `RESULT.json` under a fresh `REPORT/runtime_normalization/<namespace>`. It does not select operating profiles, rebuild the whole-study physical inventory or calculate new scientific scores. Tail completion means the original admitted full-source cursor/journal and research finalization evidence; it is not first/last-word correctness.

## PowerShell

Run actual preparation/analysis only after root confirms native closure and releases the quiet interval. Every existing output is preserved; never rerun an occupied namespace. Use the original EDGE interpreter:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edge = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$helper = Join-Path $sim 'scripts\s6c_b36_v2_post_analysis_v1.py'
& $edge -B $helper checks
& $edge -B $helper prepare --observer-index 'EXACT_INDEX_PATH' 'EXACT_INDEX_SHA' --manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_fast_v2\MANIFEST.json' a19d8b5bebdc425256f8f546072b018ff5c65665a23ffab3064e75fafe7294b1
& $edge -B $helper run --request 'RETURNED_REQUEST_PATH' 'RETURNED_REQUEST_SHA' --plan 'RETURNED_PLAN_PATH' 'RETURNED_PLAN_SHA'
& $edge -B $helper normalize --spec 'EXACT_FINITE_SPEC_PATH' --spec-sha256 'EXACT_SPEC_SHA' --namespace b36_v2_actual_metadata_v1
```

## Anaconda Prompt / Command Prompt

No installation or activation is needed because the absolute interpreter selects the original environment. The bindings below must be replaced with actual reviewed values.

```bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_EDGE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "S6C_HELPER=%S6C_SIM%\scripts\s6c_b36_v2_post_analysis_v1.py"
"%S6C_EDGE%" -B "%S6C_HELPER%" checks
"%S6C_EDGE%" -B "%S6C_HELPER%" prepare --observer-index "EXACT_INDEX_PATH" "EXACT_INDEX_SHA" --manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_fast_v2\MANIFEST.json" a19d8b5bebdc425256f8f546072b018ff5c65665a23ffab3064e75fafe7294b1
"%S6C_EDGE%" -B "%S6C_HELPER%" run --request "RETURNED_REQUEST_PATH" "RETURNED_REQUEST_SHA" --plan "RETURNED_PLAN_PATH" "RETURNED_PLAN_SHA"
"%S6C_EDGE%" -B "%S6C_HELPER%" normalize --spec "EXACT_FINITE_SPEC_PATH" --spec-sha256 "EXACT_SPEC_SHA" --namespace b36_v2_actual_metadata_v1
```

Source checks cover the exact code/private-context boundaries, fixed V2 manifest and research generation, and rejection of unrelated recovery, physical inventory, repeated requests or result paths. They use tiny fixtures; no actual preparation, native admission, audio, model or policy computation is run by checks. The ordinary original actual conversion still enforces its native payload/source/timing/parity checks after the inventory admits a closed batch.

