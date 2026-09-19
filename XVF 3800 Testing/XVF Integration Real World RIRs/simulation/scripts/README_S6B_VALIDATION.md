# Validate the S6B actual pilot without inference

`s6b_validation.py` checks a completed native pilot against the **frozen** application scheduler/tracker and exact native neural evidence. It verifies cache reuse, rejects 28 altered dependencies/artifacts, compares native and replayed decisions/transcripts, and checks causality and cue-disabled parents. It does not load neural models, call audio hardware, alter authoritative evidence, or use reference labels to predict anything.

## Inputs and outputs

`prepare` writes `reports/S6B/20260909T230840Z/validation/VALIDATION_PLAN.json`. This is an interface/fixture plan, not a test-pass claim.

`run` consumes the execution manifest (default `EPOCH2_EXECUTION_MANIFEST.json`) and actual native pilot index (default `epoch2/PILOT_NEURAL_INDEX.json`). The index must contain at least one completed native row. Every completed row in the supplied index is checked, and the receipt separately records whether the index population is complete. A partial index cannot be reported as a completed pilot.

The validator imports `s6b_execution`, `s6b_replay`, the common binding API, and application classes from the immutable epoch snapshot. It verifies snapshot and registry hashes first. It reads the actual native receipt, evidence JSON, 192-dimensional vectors, full native events and latest transcript artifact. A fresh tracker/scheduler is created for each replay; no model session is created.

The result is written to `reports/S6B/20260909T230840Z/validation/ACTUAL_PILOT_VALIDATION.json`, with code/input hashes, population, per-row comparison results, 28 cache-fault results and causal checks. A failed semantic check returns a failing receipt and nonzero exit. A missing/invalid input raises an error and must be resolved before claiming validation.

Use `--output-name FIRST_FOUR_PILOT_VALIDATION_V2.json` with an explicitly partial input index to preserve a preliminary check separately. Output names must be JSON filenames within the validation report directory. This does not change the population requirement for the final pilot receipt.

## What is compared

The canonical neural recipe profile is replayed on its exact cached observations. The validator compares every tracker decision, semantic transcript event fields, and first-display/first-final/latest final transcripts to the actual native application output. Source spans and declared modeled availability remain part of the comparison. Native wrapper wall instrumentation is excluded. Native batched release-watermark and all-lanes-closed metadata is also excluded and its difference count is reported separately, because offline replay seals each observation immediately. Those release diagnostics are neither equal nor interchangeable with physical latency.

A cutoff at the middle of the actual observation arrivals must reproduce the same already-visible prefix. Renaming unrelated case/room/truth metadata must leave decisions and transcript events unchanged. Actual cached vectors also exercise spatial-disabled exact voice-parent parity, structural same-code parent parity, and every tracker's future-prefix invariance. A temporary telemetry file containing a forbidden reference-identity field must be rejected by the real provider.

The 28 cache rejection fixtures are 18 changed identity dependencies, five changed-byte artifacts with **unchanged size and restored old modification time**, and five missing artifacts. An actual cache hit is required first. All destructive fault operations occur only on temporary copies under `simulation/staging/s6b/20260909T230840Z/validation`; the resolved temporary directory is checked to remain there. The originals are only read. Temporary files are removed automatically at completion.

The fixture count is not an empirical performance result. Quarantine/graph activation and method quality must still be reported from the full actual S6B results. Full journal coverage does not imply a ReDim observation was made for every short end fragment.

## PowerShell

Use the repository Python below from PowerShell, Command Prompt, or Anaconda Prompt. It matches the frozen native Python and NumPy versions. The validator rejects a different runtime for exact numeric parity; no dependency installation is required.

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_validation.py' prepare
```

To repeat the completed pilot without replacing its historical receipts:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_validation.py' run --epoch epoch2 --neural-index '.\reports\S6B\20260909T230840Z\validation\PILOT_NEURAL_INDEX_ALL_CACHE_IMMUTABLE.json' --output-name OPTIONAL_REPEAT_PILOT_VALIDATION.json
```

To select a particular immutable manifest/index explicitly:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_validation.py' run --manifest '.\reports\S6B\20260909T230840Z\EPOCH2_EXECUTION_MANIFEST.json' --neural-index '.\reports\S6B\20260909T230840Z\validation\PILOT_NEURAL_INDEX_ALL_CACHE_IMMUTABLE.json' --output-name OPTIONAL_REPEAT_PILOT_VALIDATION_2.json
```

## Command Prompt or Anaconda Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_validation.py" prepare
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_validation.py" run --epoch epoch2 --neural-index "reports\S6B\20260909T230840Z\validation\PILOT_NEURAL_INDEX_ALL_CACHE_IMMUTABLE.json" --output-name OPTIONAL_REPEAT_PILOT_VALIDATION.json
```

If the validator itself is run from an epoch snapshot, set the simulation root first so paths do not resolve inside staging:

```bat
set "JP_S6B_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
```

PowerShell equivalent:

```powershell
$env:JP_S6B_SIM = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
```

The comparison uses the frozen application imported by the manifest even when the validator is executed from the live scripts folder. Do not edit the frozen application or actual evidence while a validation or native run is active. A later paced comparison uses a separately reserved native worker and selected finalists; this model-free validator does not launch it.

## Completed pilot verification

The authoritative epoch2 pilot passed on all 64 completed native rows: 1,323 tracker decisions, 2,605 semantic transcript events and 144 final utterances matched. All 64 causal cutoff/metadata-renaming checks passed, as did the 28 cache fault fixtures and 59 parent/prefix/future-cue/schema assertions on 23 actual cached seed vectors. The initial run took 16.29 seconds with zero neural calls. Its `ACTUAL_PILOT_VALIDATION.json` is preserved unchanged.

The final packaging receipt is `ACTUAL_PILOT_VALIDATION_FINAL.json`, created by a 23.79-second model-free repeat against `PILOT_NEURAL_INDEX_ALL_CACHE_IMMUTABLE.json`. It passes the same 64 rows with identical native/parity/causality results. `PILOT_INDEX_LINEAGE.json` and `.md` resolve the earlier index hash to its exact immutable invocation-completion bytes. The convenience `epoch2/PILOT_NEURAL_INDEX.json` was replaced by a later all-cache closure; this was an index-metadata change, not new inference. Both index versions and historical validation remain available. Use an immutable index and a new output name for future checks. This validates the bounded pilot; it is not an all-bank method-quality conclusion.

`FIRST_FOUR_PILOT_VALIDATION.json` preserves an initial over-strict comparison that counted expected native/replay release-batching metadata differences. `FIRST_FOUR_PILOT_VALIDATION_V2.json` uses the documented semantic comparison and passes. Source spans, text, labels and declared availability were never relaxed to achieve parity.
