# Provisional candidate decisions overlay V1

This bounded reporting helper updates the 240-ID working disposition using completed, reviewed offline interpretations. It performs no models, policy replay, scoring, inventory walk, raw-event reading, audio/model hashing or runtime analysis. It does not finalize representative or operating selection.

## Inputs

- candidate_disposition/PROVISIONAL_DECISIONS_SOURCE_PLAN_V1.json: explicit path, byte length and SHA-256 for each small source buffer.
- Exact working V1 receipt and 240-row CSV; exact final assembly plan V2 and final assembler source vocabulary. Original 160 registration rows and all 240 working rows remain untouched.
- Compact N03/N08N10/N12/cross interpretations, source/core/native closure receipts, token/strata review and conditional enrollment/cold-warm interpretation. Referenced raw/scored tables are not traversed.

Every input is metadata or source under SIM, at most 3 MiB. Input SHA/length is checked against the actual buffer parsed. Missing, changed, duplicate or malformed IDs/metadata fail closed. Full native scopes remain separate source references; this helper does not count native sessions from scores. Original evidence references remain inherited historical authority.

## Outputs

A fresh directory under REPORT/candidate_disposition contains:

- CANDIDATE_DECISIONS_PROVISIONAL.json: all 240 IDs, original row fingerprints/routes, proposed final scientific vocabulary, interpretation/limits, evidence references and unresolved runtime dependencies.
- WORKING_ROWS_UNCHANGED.csv: exact byte copy of the immutable working CSV.
- EXPLANATION.md: concise scope and merge instructions.
- RECEIPT.json: source plan/helper/README/output bindings and exact validation counts.

All decisions remain resolved:false; operating_presets is empty and final assembly readiness is false. The four prospective O0/O0 bundles are dependencies, not selected presets. A target directory that already exists is rejected; choose a new output suffix to reproduce.

## PowerShell

Use the dedicated analysis interpreter; no environment activation or model environment is required.

~~~powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$analysisPython = Join-Path $sim 'staging\s5_text_metrics\analysis_env\Scripts\python.exe'
$report = Join-Path $sim 'reports\S6C\20260910T123540Z'
& $analysisPython (Join-Path $sim 'scripts\s6c_candidate_decisions_overlay_v1.py') --source-plan (Join-Path $report 'candidate_disposition\PROVISIONAL_DECISIONS_SOURCE_PLAN_V1.json') --output (Join-Path $report 'candidate_disposition\provisional_decisions_v1_reproduction')
~~~

## Anaconda Prompt / Windows CMD

Anaconda activation is unnecessary because the exact interpreter path is explicit.

~~~bat
set "JP_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "JP_REPORT=%JP_SIM%\reports\S6C\20260910T123540Z"
"%JP_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%JP_SIM%\scripts\s6c_candidate_decisions_overlay_v1.py" --source-plan "%JP_REPORT%\candidate_disposition\PROVISIONAL_DECISIONS_SOURCE_PLAN_V1.json" --output "%JP_REPORT%\candidate_disposition\provisional_decisions_v1_reproduction"
~~~

## Merge into final reporting

Join on exact candidate ID; retain every original working column. Treat proposed_final_scientific_disposition as an unresolved proposal for the assembler's scientific_disposition. Interpretation source IDs are not the assembler's evidence IDs. A later finite resources/evidence graph must prove each candidate, exact route, population and closure through the original assembler guards. Do not derive full coverage by union or propagate C065 execution to C083/C084 aliases.

Complete actual main paced coverage is required before REPRESENTATIVE_EVALUATED. Final operating bundles require matching actual paced and continuous evidence, independent requirement resolution and root selection. The assembler input schema/status must be created separately; this overlay intentionally cannot be submitted as a ready final input.

The overlay supersedes only the relevant stale pending-full interpretation fields, not original rows or settings. Panel-only, admission-limited, unactivated mechanism, oracle/null and conditional enrollment limitations remain explicit. Full first-display, first-final, latest-cp, mixed word metrics and separate source-support denominators must retain their original meanings. C065 no-gallery control preparation does not make it an operating fallback.

