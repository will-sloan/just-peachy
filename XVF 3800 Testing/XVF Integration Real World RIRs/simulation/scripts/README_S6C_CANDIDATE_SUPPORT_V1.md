# Candidate support inventory

Purpose: build a working coverage table for all 196 new C candidates and 44 preserved B controls from explicitly admitted completed analysis receipts and their exact COVERAGE.csv files. This is a reporting helper. It does not execute models, replay policy, read individual score/prediction payloads, select candidates, or count physical runs.

Inputs: an explicit JSON specification with schema `s6c-candidate-support-spec.v1`, status `APPROVED_EXPLICIT_SUPPORT_SNAPSHOT`, exact path/bytes/SHA256 bindings for `c_registry` (final V7), `b_design` (original registered design), and `input_index` (480 views / 240 scenes). Each `authorities` entry supplies a unique `source_id`, `authority` binding, `expected_schema`, `expected_status`, `coverage_pointer` such as `/tables/9`, `scored_count_field`, `identity_mode` (`explicit_column` or explicitly inherited `historical_same_tap`), `repetition` (0 for non-repeated studies), `scope_label`, and `execution_scope`. Actual paced entries use `ACTUAL_SOURCE_PACED_NATIVE`; other scope labels must accurately describe their source. No directory discovery or missing-source substitution occurs.

The collector validates exact receipt/coverage bytes, requested and scored counts, unique route/scene rows, registered routes and original scene IDs. Unknown candidates, scenes, statuses, changed sources and ambiguous schemas fail. Repeated authority paths/digests and repeated coverage-table paths are rejected even under different source IDs. Equal coverage bytes at different paths can belong to distinct completed experiments/repetitions; those authorities remain separate, with equal_coverage_content_groups disclosed in the receipt. Equal content is not inferred to be an additional physical run or an alias. Declared authority references include failed/unscored rows, while scored_authority_references counts only authorities with at least one scored case on that route. Candidates with only failed/unscored rows are explicitly marked DECLARED_AUTHORITIES_WITH_NO_SCORED_CASES. A source route gets full-bank support only when its own scored set equals all 240 scenes. A union of smaller panels is reported as coverage only. Repetition indices must be supplied separately; duplicates within one authority are rejected. A scored coverage record does not imply that all reference words are complete or that every metric was eligible.

Outputs in a fresh directory: CANDIDATE_SUPPORT_WORKING.csv (all 240 candidates), AUTHORITY_ROUTE_SUPPORT.json (exact per-authority route populations/statuses/bindings), and RECEIPT.json. Missing support is explicit. Final disposition remains pending; aliases are not propagated and physical inference count remains null. A separate reviewed scientific disposition and execution inventory are required for the final handoff. Successful collector status does not mean the study is complete. Existing outputs are never overwritten.

Each input is limited to 128 MiB. Parsed source bytes are retained once per call under matching bindings. The helper requires no external libraries.

PowerShell:

```powershell
$simTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$pythonTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $pythonTask -B "$simTask\scripts\s6c_candidate_support_v1.py" checks --output "$simTask\reports\S6C\20260910T123540Z\independent_review\CANDIDATE_SUPPORT_CHECKS_V1.json"
# After the exact explicit specification is reviewed:
& $pythonTask -B "$simTask\scripts\s6c_candidate_support_v1.py" run --spec 'C:\exact\SPEC.json' ACTUAL_SPEC_SHA256 --output "$simTask\reports\S6C\20260910T123540Z\candidate_support\working_v1"
```

Anaconda Prompt / Windows CMD:

```bat
set "S6C_SUPPORT_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_SUPPORT_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6C_SUPPORT_PY%" -B "%S6C_SUPPORT_SIM%\scripts\s6c_candidate_support_v1.py" checks --output "%S6C_SUPPORT_SIM%\reports\S6C\20260910T123540Z\independent_review\CANDIDATE_SUPPORT_CHECKS_CMD_V1.json"
"%S6C_SUPPORT_PY%" -B "%S6C_SUPPORT_SIM%\scripts\s6c_candidate_support_v1.py" run --spec "C:\exact\SPEC.json" ACTUAL_SPEC_SHA256 --output "%S6C_SUPPORT_SIM%\reports\S6C\20260910T123540Z\candidate_support\working_cmd_v1"
```

No Conda activation or installation is necessary. Replace example paths and hashes with bound local evidence. Checks use synthetic rows/files only and exercise duplicates, failure versus scoring, partial/full populations, route schemas and exact-buffer admission.


Independent prospective review found duplicate authority aliases and an all-failed support label. Both were repaired before actual export; prior source/README/check receipt bytes are preserved under staging/s6c/20260910T123540Z/candidate_support/before_review_repair_v1. Independent whole-run synthetic fixtures verify these paths in addition to the 14 small checks.

The second prospective review refined equal-content handling: coverage byte equality alone cannot collapse distinct completed repetitions or experiments. The intermediate overly strict draft is preserved under candidate_support/before_equal_content_repair_v2.

Actual historical IDs are B00 through B39 plus B18_C1, B20_C1, B24_FREQUENT and B24_SPARSE, as bound by the original registered design and its historical registry authority. They are not a synthetic consecutive B00-B43 range. The first actual reporting invocation stopped on that incorrect guard before coverage reads or output creation; WORKING_V1_ENTRY_FAILURE.json and prior source bytes are preserved. The repaired collector uses the exact actual set.
