# Final evidence input preparation

`s6c_final_evidence_inputs_v1.py` prepares an unresolved input assembly for the unchanged final disposition assembler. It preserves all240 exact candidate IDs,388 C routes, original working rows, and all46 requirement rows. It neither selects operating profiles nor certifies stage completion.

## Inputs

Exact pinned V2 assembly plan, working/provisional receipts, original compact scoring/native-authority ledger, completed later N08/N10/N12/cross receipts, the596 timing input authority and its16 original normalization authorities, and the completed five-long normalization/diagnostic receipts. The original requirement CSV and source index are copied as nested original rows with their row hashes. Bindings come from the same buffers parsed. Maximum input is32MiB; no prediction, audio, raw log, model, per-cell scientific result or score-value table is opened.

Original COVERAGE.csv files are referenced through their completed analysis receipts for the final assembler to read later. This preparation does not recompute or independently reread their case rows. Original full-bank membership from the working authority is retained per authority; later full membership is taken from exact completed receipts. No union of panels becomes full confirmation.

Native RESULTS metadata exposes actual job keys and COMPLETE/COMPLETE_REUSED rows. It does not establish physical attempt totals, which require the final census. Runtime rows are the existing typed normalizer output; exact condition/owner/tail and unique native-result hash joins are checked. MAIN520, cadence24, arrival12, cross40 and continuous5 stay separate. Historical B00 tail means source journal/cursor completion, not an unlogged dispatch certificate. The shared B00/B01 normalization authority is admitted once even though the timing inputs refer to it twice. Historical runtime conditions preserve their additional actual-profile and generation fields; the required original registration digest and route are verified against working metadata.

The first preparation stopped before any output publication on overly strict historical whole-dictionary equality. Its source/README are preserved under STAGING/final_evidence_inputs/before_historical_condition_v1. The correction retains required-field equality plus the entire actual historical condition, and deduplicates only identical normalization authority/cohort references. No original result or evidence was changed.

## Outputs

Use a fresh immediate child of REPORT/candidate_disposition. Immutable outputs:

- FINAL_INPUTS_UNRESOLVED.json: original assembler schema with exact resource projections, available source evidence and unresolved root decisions.
- CANDIDATE_EVIDENCE_MAP.json: all240 source scopes, including per-authority route/count/reuse/membership distinctions.
- REQUIREMENT_RESOLUTION_INPUTS.json: all46 original obligation rows and explicit current dependencies, unresolved.
- ASSEMBLY_NOTES.md and PREPARATION_RECEIPT.json: interpretation boundaries, counts, exact source/output hashes.

No output is READY_FOR_FINAL_ASSEMBLY. Physical rows, final46 requirement/artifact acceptance and root candidate/operating selection remain pending. Root must prepare a new resolved input; never edit this output into a past success. The final assembler must verify all resource hashes and actual projection rows, including the deferred original coverage metadata. Prospective B36/C067/C088/C091 O0 bundles remain selected=false; C065 is a control. The helper does not create missing native proofs for panel-only families or alias C083/C084.

## PowerShell

Use the existing EDGE interpreter; no install or environment activation. This is metadata preparation only:

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B s6c_final_evidence_inputs_v1.py --output "$simRoot\reports\S6C\20260910T123540Z\candidate_disposition\final_inputs_working_v1"
```

## Anaconda Prompt / CMD

Run the exact existing interpreter without activating a different environment:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_evidence_inputs_v1.py --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\candidate_disposition\final_inputs_working_v1"
```

Existing output namespaces fail before publication; choose a fresh suffix for reproduction. Source checks cover exact240/388/46 IDs, duplicate/nonfinite JSON, source joins, alias limits, unique native cells, exact typed runtime conditions,596+5 totals and prospective main/long equality. No scoring/native invocation, resource scan, census or acceptance is performed. Read the held final assembler README for its separate final validation command; this unresolved input is deliberately rejected by that command.
