# Admit the remaining S6D bank after telemetry recovery

Purpose: derive a fresh60-stage serial bank from the interrupted bank_queue_v3 without repeating its16 successful MAIN cases. The old failed17 remains charged and excluded; a separate17_R2 and fresh pre-QA_R3 are added. Every other pending original source/profile/gain/guard and completion gate is retained. The first resumed body has14 attempts. All totals are52existing plus378future =430attempts and19744.058charged seconds.

Inputs: exact root-accepted telemetry V2/owner V7 source review with status `ROOT_ACCEPTED_TELEMETRY_RECOVERY_V2_SOURCES_V2` and canonical owner/bridge/policy bindings; the final combined execution source freeze and its literal SHA256; the actual successful recovery.v2 output; inherited gain-only recovery; exact52-entry ledger; interrupted queue/approval/20plans; and the16-case whole-audio review. The source review must bind the same freeze under `owner_execution_source_freeze`. V7's file-only prior_closure must validate both recovery kinds before any plan output is written. The helper opens no audio and issues no hardware command. These new V7 authority inputs must exist and be root accepted before execution; placeholders are not authorization.

Outputs: fresh runner/bank_queue_v4 with20 plans/authorizations,60 jobs, reviewed hashes,20 read-only owner check-plan logs and ROOT_QUEUE_REVIEW.json. Existing outputs are refused. Metadata admission is not launch: root must independently inspect the literal378-row difference and use the existing admitted-queue launcher only after recovery and source checks.

Owner authorizations use only the24 canonical `owner_execution_dependency_bindings` in the exact combined freeze. Every dependency is verified, filenames must be collision-free under Windows case folding, and the list must include the exact reviewed owner/bridge/policy bindings. Historical producer copies remain in nested recovery proofs; they are not merged into the owner's flat snapshot or newly flattened into runner bindings. The case-folding helper retains the first canonical path for identical-byte duplicates and rejects conflicting bytes; the current execution graph additionally rejects any duplicate basename. Plans, authorizations and the receipt bind this freeze and admission helper/README. Existing historical runner guards are retained.

The first group's authorization charge is recomputed from its16 remaining rows:715.461seconds, replacing the old32-row1504.922 declaration. Other groups retain their original count and charge. No charge or attempt is removed from the52-entry historical ledger.

PowerShell (root only; replace all final V7 authority placeholders with the independently accepted paths/hash):

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$sourceReview='<ROOT_ACCEPTED_V7_SOURCE_REVIEW_PATH>'
$executionFreeze='<FINAL_V7_COMBINED_SOURCE_FREEZE_PATH>'
$executionSha='<EXACT_FINAL_V7_FREEZE_SHA256>'
$recovery='<ACTUAL_SUCCESSFUL_RECOVERY_V2_PATH>'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_bank_remaining_admit_v2.py" --source-review $sourceReview --execution-freeze $executionFreeze --execution-freeze-sha256 $executionSha --recovery $recovery
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "SOURCE_REVIEW=<ROOT_ACCEPTED_V7_SOURCE_REVIEW_PATH>"
set "EXECUTION_FREEZE=<FINAL_V7_COMBINED_SOURCE_FREEZE_PATH>"
set "EXECUTION_SHA=<EXACT_FINAL_V7_FREEZE_SHA256>"
set "RECOVERY=<ACTUAL_SUCCESSFUL_RECOVERY_V2_PATH>"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_bank_remaining_admit_v2.py" --source-review "%SOURCE_REVIEW%" --execution-freeze "%EXECUTION_FREEZE%" --execution-freeze-sha256 "%EXECUTION_SHA%" --recovery "%RECOVERY%"
```

The original480-attempt/21600-second/40GiB payload caps, C50GiB/G75GiB floors, all job watchdogs, September16 deadline and45-minute reserve remain. This helper installs no automation, does not change device settings or model code, and does not resolve the failed batch by rewriting history. Post-QA, source-epoch effects, final catalog admission and scientific efficacy remain separately reviewed.
