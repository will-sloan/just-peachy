# Fast-observer post-analysis adapter V1

This one helper admits explicit fast-observer receipts for six existing post-analysis routes. It reuses the original scientific converter/diagnostic functions. No native worker, APP, model, scoring formula, name/context metric, historical generation, or repetition semantics change.

The helper is source-held for review. Its checks do not read an actual observer index, runtime manifest, prediction, native log, audio or model. No real analysis preparation or execution has been performed.

The exact V7 dependency is SHA256 `fc23ff6650a34c927211d142e61b9dcf7afe7ee07e832c51573ae2da0dc3c7a3`. Its separate source/context review is `REPORT/independent_review/INVENTORY_V7_FAST_CONTEXT_REVIEW_V1.json`; this does not certify actual runtime closure.

## Choose the original analysis family

| --kind | Unchanged original helper | Output family | Required prepare inputs |
|---|---|---|---|
| canonical | s6c_paced_analysis_v1.py | paced_analysis | --manifest PATH SHA; --index PATH SHA |
| sentinel | s6c_paced_sentinel_analysis_v1.py | paced_arrival_analysis | --manifest PATH SHA; --index PATH SHA |
| cross | s6c_paced_cross_analysis_v1.py | paced_cross_analysis | --manifest PATH SHA; --index PATH SHA |
| historical | s6c_historical_paced_analysis_v1.py | historical_paced_analysis | --manifest PATH SHA; --generation baseline or research |
| long_c | s6c_long_diagnostics_v1.py | long_diagnostics | one or more --admission PATH SHA |
| long_b36 | s6c_long_b36_diagnostics_v1.py | long_b36_diagnostics | --manifest PATH SHA |

Every prepare command also requires `--namespace NAME_fast_v1` (or `NAME_fast_v2`) and `--observer-index PATH SHA`. Names must be fresh, simple and at most 60 characters. Existing namespace families are retained. Unused mode-specific options reject.

Historical baseline means the exact original B00 source and retained timing scope. Historical research means the original B01/B36 frozen S6B generation. Run them separately; no B36 or v3 substitution for B00. The original converter keeps every repetition separate. Sentinel and cross retain their exact selection and different route roles. Continuous diagnostics remain actual continuous observations; they do not become canonical-scene predictions or fresh correctness scores.

## Exact input contracts

Use the completed runtime's actual bindings, not guessed paths or current draft files:

- `--observer-index` is the exact JSON binding with schema `s6c-fast-observer-index.v1`, status `COMPLETE_METADATA_ENUMERATION`, and `receipts` list. V7 validates every attached observer receipt and associates it with the relevant closed execution. This wrapper does not convert a metadata enumeration into a completion claim.
- `--manifest` and `--index` are the exact prepared native manifest and completed paced index expected by the selected original converter.
- C-long `--admission` points to each actual outer invocation ADMISSION.json with its exact SHA. Do not pass C-long manifests through the paced-manifest interface.
- A new immutable REQUEST.json records the family, namespace, exact index/manifest/admission bindings and current adapter/V7 sources. Its binding and the observer-index binding are added to the unchanged original PLAN's source list.
- The original prepare function performs its original closed-native, source, generation, gallery, parity and metadata admission. Failed preparation keeps its failure record and the new request; no source is overwritten.
- Run takes only the exact `--request PATH SHA` and `--plan PATH SHA` returned by prepare. These are explicit, mutually bound inputs. Changing the observer index, original plan, native input bindings, source code or README invalidates the prepared context.

All wrapper inputs are exact, same-buffer, bounded code/JSON metadata. The original converters retain their own streaming/native-observation bounds. A valid prepared plan still does not prove the subsequent scientific conversion succeeded.

## Private context and code identity

The adapter uses `types.FunctionType` to give a few original orchestration/metadata functions a private globals dictionary while keeping the exact same `__code__` object, defaults and closures. Existing sentinel/cross namespace adaptations are reused unchanged. The original modules and their global dictionaries are not monkeypatched.

A per-invocation V7 `base.MetadataReader` factory calls `admit_observer_index(reader, binding)` before returning the reader. Each reader has its own explicit observer context. V7 still owns source/owner/closure validation; its legacy admission APIs remain available. Fast-family checks run on actual admission during both preparation and execution and reject another family or a legacy non-fast source.

Only the inventory factory, source-binding callback and input-binding checks differ in the private context. C-long also uses the identical original `admit_closed` code with the private V7/base proxies. B36-long's original small metadata readers receive the same binding check so the explicit prepared input cannot change between the wrapper and the original reader. Scientific functions/classes remain the original objects, including transcript/name/context conversion, shared logical parity, statistical observations, stream parsing and original-generation handling. Checks record code signatures and object identity rather than claiming numerical equivalence from newly calculated scores.

Sources and original worker/APP code are preserved. The helper does not install dependencies, change model weights, regenerate data, acquire hardware, start native jobs or grant permission for a paced session.

## PowerShell

Use the already installed EDGE interpreter. First set the paths once:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$report = "$sim\reports\S6C\20260910T123540Z"
$python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$helper = "$sim\scripts\s6c_fast_observer_analysis_v1.py"
& $python -B $helper checks
```

Set these variables to the actual completed bindings from the selected closed run. The uppercase example values below are placeholders to replace, not existing paths or hashes:

```powershell
$observerIndex = 'ABSOLUTE_OBSERVER_INDEX_JSON_PATH'
$observerSha = 'EXACT_OBSERVER_INDEX_SHA256'
$manifest = 'ABSOLUTE_CLOSED_MANIFEST_JSON_PATH'
$manifestSha = 'EXACT_MANIFEST_SHA256'
$completedIndex = 'ABSOLUTE_COMPLETED_PACED_INDEX_JSON_PATH'
$completedIndexSha = 'EXACT_COMPLETED_INDEX_SHA256'
```

Canonical, sentinel and cross use the same options; select only the matching family:

```powershell
& $python -B $helper prepare --kind canonical --namespace chosen_analysis_fast_v2 --observer-index $observerIndex $observerSha --manifest $manifest $manifestSha --index $completedIndex $completedIndexSha
# For another independently selected run, use --kind sentinel or --kind cross and a fresh namespace.
```

Historical baseline/research use separate fresh namespaces:

```powershell
& $python -B $helper prepare --kind historical --namespace original_b00_fast_v1 --observer-index $observerIndex $observerSha --manifest $manifest $manifestSha --generation baseline
& $python -B $helper prepare --kind historical --namespace original_research_fast_v1 --observer-index $observerIndex $observerSha --manifest $manifest $manifestSha --generation research
```

Continuous modes:

```powershell
$admission = 'ABSOLUTE_CLOSED_C_LONG_INVOCATION_ADMISSION_JSON_PATH'
$admissionSha = 'EXACT_C_LONG_ADMISSION_SHA256'
& $python -B $helper prepare --kind long_c --namespace continuous_c_fast_v2 --observer-index $observerIndex $observerSha --admission $admission $admissionSha
# Additional independently closed C-long admissions use another --admission PATH SHA pair.
& $python -B $helper prepare --kind long_b36 --namespace continuous_b36_fast_v1 --observer-index $observerIndex $observerSha --manifest $manifest $manifestSha
```

Run only after preparation succeeds, using the exact returned bindings:

```powershell
$request = 'ABSOLUTE_RETURNED_REQUEST_JSON_PATH'
$requestSha = 'EXACT_RETURNED_REQUEST_SHA256'
$plan = 'ABSOLUTE_RETURNED_ORIGINAL_PLAN_JSON_PATH'
$planSha = 'EXACT_RETURNED_ORIGINAL_PLAN_SHA256'
& $python -B $helper run --request $request $requestSha --plan $plan $planSha
```

## Anaconda Prompt / CMD

No Conda installation is needed; these commands use the existing exact interpreter:

```bat
set "JP_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "JP_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_HELPER=%JP_SIM%\scripts\s6c_fast_observer_analysis_v1.py"
"%JP_PYTHON%" -B "%JP_HELPER%" checks
set "JP_OBSERVER=ABSOLUTE_OBSERVER_INDEX_JSON_PATH"
set "JP_OBSERVER_SHA=EXACT_OBSERVER_INDEX_SHA256"
set "JP_MANIFEST=ABSOLUTE_CLOSED_MANIFEST_JSON_PATH"
set "JP_MANIFEST_SHA=EXACT_MANIFEST_SHA256"
set "JP_INDEX=ABSOLUTE_COMPLETED_PACED_INDEX_JSON_PATH"
set "JP_INDEX_SHA=EXACT_COMPLETED_INDEX_SHA256"
"%JP_PYTHON%" -B "%JP_HELPER%" prepare --kind canonical --namespace chosen_analysis_fast_v2 --observer-index "%JP_OBSERVER%" "%JP_OBSERVER_SHA%" --manifest "%JP_MANIFEST%" "%JP_MANIFEST_SHA%" --index "%JP_INDEX%" "%JP_INDEX_SHA%"
rem Use matching --kind sentinel or --kind cross for those separate populations.
"%JP_PYTHON%" -B "%JP_HELPER%" prepare --kind historical --namespace original_b00_fast_v1 --observer-index "%JP_OBSERVER%" "%JP_OBSERVER_SHA%" --manifest "%JP_MANIFEST%" "%JP_MANIFEST_SHA%" --generation baseline
"%JP_PYTHON%" -B "%JP_HELPER%" prepare --kind historical --namespace original_research_fast_v1 --observer-index "%JP_OBSERVER%" "%JP_OBSERVER_SHA%" --manifest "%JP_MANIFEST%" "%JP_MANIFEST_SHA%" --generation research
set "JP_ADMISSION=ABSOLUTE_CLOSED_C_LONG_INVOCATION_ADMISSION_JSON_PATH"
set "JP_ADMISSION_SHA=EXACT_C_LONG_ADMISSION_SHA256"
"%JP_PYTHON%" -B "%JP_HELPER%" prepare --kind long_c --namespace continuous_c_fast_v2 --observer-index "%JP_OBSERVER%" "%JP_OBSERVER_SHA%" --admission "%JP_ADMISSION%" "%JP_ADMISSION_SHA%"
"%JP_PYTHON%" -B "%JP_HELPER%" prepare --kind long_b36 --namespace continuous_b36_fast_v1 --observer-index "%JP_OBSERVER%" "%JP_OBSERVER_SHA%" --manifest "%JP_MANIFEST%" "%JP_MANIFEST_SHA%"
set "JP_REQUEST=ABSOLUTE_RETURNED_REQUEST_JSON_PATH"
set "JP_REQUEST_SHA=EXACT_RETURNED_REQUEST_SHA256"
set "JP_PLAN=ABSOLUTE_RETURNED_ORIGINAL_PLAN_JSON_PATH"
set "JP_PLAN_SHA=EXACT_RETURNED_ORIGINAL_PLAN_SHA256"
"%JP_PYTHON%" -B "%JP_HELPER%" run --request "%JP_REQUEST%" "%JP_REQUEST_SHA%" --plan "%JP_PLAN%" "%JP_PLAN_SHA%"
```

## Outputs and limits

The new request is under `fast_post_analysis_admission/<kind>/<namespace>/REQUEST.json`. Original PLAN, per-cell observations/predictions or continuous diagnostics, repetition indices and final receipts stay in the corresponding original analysis family under the fresh fast namespace. Original result schemas remain unchanged; the bound source list records this observer-aware adapter. Original failure preservation and quiet-lease checks remain operative.

Prepare/run refuse an active paced quiet lease. Do not launch post-analysis until the parent coordinator releases quiet and authorizes the exact completed inputs. Code/context checks are small and do not constitute permission to read active evidence.

No new neural inference is performed. Paced converters retain their original policy parity replay; continuous diagnostics retain their original no-policy/no-scene-scoring scope. Observed wall emissions, source-attributed timing, modeled lane readiness and sampled resource peaks remain distinct. Missing samples are not imputed, nested phase costs are not summed into total runtime, and no CM5 or GUI/phonetic latency claim is added.

