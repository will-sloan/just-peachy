# Cold and warm naming queries from completed tables

Purpose: s6c_cold_warm_naming_v1.py closes the handoff's cold-versus-warm query summary using two already completed full-bank naming analyses. The six original/calibrated/real-cue naming conditions and the six common-roster duration conditions remain separate authorities. It neither rescored outcomes nor changes the predictor, gallery, candidate, threshold or any source table.

Inputs are the exact existing NAME_ANALYSIS_RECEIPT.json, QUERIES.csv and COVERAGE.csv under full_n01_naming_names_v3 and full_n01_common_duration_names_v3. Both original authorities are pinned in source: each has 2,880 completed case/routes, six profiles, 240 cases and both taps. The original V3 name scorer code hash is checked as a declared dependency, not imported or executed. The helper verifies and parses each exact CSV byte buffer once, checks the complete coverage grid, and accounts for every executed query row. It does not open predictions, individual name scores, native logs, retirement snapshots, PCM, models or actual process state. Original query CSVs remain retained and hash-bound in their original locations; no bulky duplicate of them is needed.

Outputs in a fresh direct REPORT child are:

- CASE_QUERY_COUNTS.csv: all 5,760 authority/case/routes, including explicit zero-executed-query cells.
- PROFILE_QUERY_COUNTS.csv: each authority/profile/ASR-tap/identity-tap query count and outcome partition.
- COLD_WARM_QUERY_SUMMARY.csv: authority/profile/taps/roster and exported cold/warm/unavailable history.
- FIRST_REFERENCE_PERSON_QUERY_SUMMARY.csv: separate first identifiable person-query, subsequent person-query and unidentifiable-reference groups.
- REFERENCE_STATUS_QUERY_SUMMARY.csv: original reference status retained alongside roster and cold/warm.
- ALL_EXPORTED_STATUS_COUNTS.csv: every combination of original raw gallery, tier, roster, cold flag/status, reference/assignment status, evidence kind and first-track/first-person flags, including blank fields.
- RESULT.json: exact source bindings, all-row closure counts, small profile summaries, per-authority scope, code/README and output hashes.
- The optional --test/--check-receipt mode writes only a fresh source-bound model-free fixture receipt.

Correct, wrong-known and unknown-name counts partition queries with one identifiable reference person. Unidentifiable queries stay separately in the total query denominator, rather than becoming unknown names or errors. Percentages use the explicitly exported identifiable-query denominator. Reference status ONE_REFERENCE_PERSON means one metadata identity intersects the query span; it does not guarantee active speech across the entire span. Incomplete references, no reference activity and multi-person spans stay distinct. Correct assignments are not necessarily confirmed or stable names, because those states are not exported in QUERIES.csv.

Cold means a new or retired resolver name state, according to the original scorer export. A new lifetime tracker ID and first identifiable query for a reference person are separate flags. The first-person flag resets in each fresh scene/profile/tap session; it is not a person's first speech or first-ever occurrence across the bank. First flags are checked against the table's own chronological query order, without inventing skipped decisions or reconstructing retirement history. Missing/truncated cold-warm statuses remain unavailable. The helper cannot independently detect a raw missing-history field that was not exposed by the original scorer; that limitation is retained explicitly.

These are overlapping executed query opportunities over cached policy projections of actual native evidence. They are not unique speech seconds, elapsed wall time, independent trials, a person-level false-accept probability or actual native-paced query measurements. The two authorities and all candidate/tap routes remain separate. Unique-clean seconds and disjoint counts are cumulative per-query state observations: only observed/missing counts and min/median/max are reported, never a sum purporting to be new speech. Row membership hashes use source row ordinals and exact parsed CSV strings; they do not replace the raw source-file SHA.

## PowerShell

Use the existing ANALYSIS interpreter. No package installation or native environment change is required.

~~~powershell
$s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = "$s6cSim\reports\S6C\20260910T123540Z"
$s6cAnalysisPython = "$s6cSim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $s6cAnalysisPython -B "$s6cSim\scripts\s6c_cold_warm_naming_v1.py" --test --check-receipt "$s6cReport\independent_review\COLD_WARM_QUERY_HELPER_CHECKS_V1.json"
& $s6cAnalysisPython -B "$s6cSim\scripts\s6c_cold_warm_naming_v1.py" --output-subdir cold_warm_naming_v1
~~~

## Anaconda Prompt or Windows CMD

~~~bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%S6C_SIM%\reports\S6C\20260910T123540Z"
set "S6C_ANALYSIS_PYTHON=%S6C_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%S6C_ANALYSIS_PYTHON%" -B "%S6C_SIM%\scripts\s6c_cold_warm_naming_v1.py" --test --check-receipt "%S6C_REPORT%\independent_review\COLD_WARM_QUERY_HELPER_CHECKS_V1.json"
"%S6C_ANALYSIS_PYTHON%" -B "%S6C_SIM%\scripts\s6c_cold_warm_naming_v1.py" --output-subdir cold_warm_naming_v1
~~~

Use fresh receipt and output names for later reproductions. Existing output is refused; failures remain partial evidence rather than overwritten success. --test runs only tiny synthetic CSV-shaped dictionaries, including missing/truncated history, new-track versus first-person distinctions, zero-query cases, unidentifiable reference, missing versus zero metadata and authority separation. Run actual table aggregation as the single analysis worker, outside quiet paced measurement. A newly closed full native core/comparison index has priority. Any later native or paced query summary requires its own explicit source and clock admission; this helper does not silently broaden its authority.

