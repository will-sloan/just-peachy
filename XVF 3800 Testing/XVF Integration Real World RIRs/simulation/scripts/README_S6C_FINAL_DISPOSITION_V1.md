# Final S6C disposition metadata assembler V1

This reporting helper preserves every cell of the 240-row working disposition, the exact original 160-row CSV, and all 388 registered C route settings. It appends separate score, native, physical, paced, continuous-session, scientific and operating overlays. It does not run models, replay policies, score predictions, scan execution directories, read raw logs/audio, select candidates automatically or certify the whole campaign.

The input is an explicit finite metadata manifest. No final assembly has been executed. A generated template is deliberately unresolved. A complete table requires all mandatory authorities and 2–4 exact operating/fallback conditions with completed main paced and actual 30–60-minute continuous evidence. A diagnostic six-case run or a prepared plan cannot qualify an operating preset.

## Inputs and authority boundaries

The assembly plan is pinned to `candidate_disposition/FINAL_DISPOSITION_ASSEMBLY_PLAN_V2.json` (SHA256 `f6b19c7070a266a775b13fac4464557910e70680c9c5f9efa58c8df67dc8980f`). The original working receipt is pinned to `working_v1/RECEIPT.json` (SHA256 `5d84d493a377eb7b991e821cf59e412da5103ba7e17786e197bb2dd9c1ecc8dd`). Every original output is re-admitted through that receipt. B IDs are B00–B39 plus B18_C1, B20_C1, B24_FREQUENT and B24_SPARSE; C IDs are C001–C196.

Each source binding has an absolute `path`, exact `bytes` and `sha256`. The same bytes are parsed and checked. Sources are explicitly listed JSON/CSV/Markdown metadata, at most 32 MiB each. No implicit source discovery or mutable path substitution occurs. Duplicate JSON/CSV keys, conflicting bindings, duplicate candidate rows and unknown routes reject. Each original CSV cell remains a string, including blank/null encodings, settings JSON, previous dispositions and historical pending text. New evidence is appended; historical wording is not rewritten.

The final manifest schema is `s6c.final_disposition_inputs.v1`. Its fields are:

- `plan`, `working_receipt`: the pinned exact bindings.
- `resources`: an ordered finite DAG. A root has `resource_id`, `binding`, `format: "json"`, and explicit JSON-pointer `assertions` for its actual schema/status. A child additionally declares `parent`; its exact binding must occur in the admitted parent document. Child format may be JSON, CSV or text. Reuse an existing resource ID instead of repeating a path. Distinct completed authorities with equal child CSV content remain distinct; duplicate root-authority content is rejected.
- `evidence`: separately scoped records, described below. Do not aggregate repeated studies or substitute a scoring authority for native execution.
- `candidate_decisions`: exactly 240 explicit records with `candidate_id`, `scientific_disposition`, `interpretation`, `limitations`, `evidence_ids` and `resolved: true`. All evidence for a candidate must be referenced. C083/C084 cannot acquire their parent's score/native/runtime evidence.
- `operating_presets`: 2–4 explicit exact conditions, each with `preset_id`, `candidate_id`, `condition`, `status` (RETAINED_OPERATING_PRESET or RETAINED_FALLBACK), `reason`, `paced_evidence_id` and `long_evidence_id`.
- `required_evidence_ids`: a nonempty, unique finite list of mandatory completed evidence. Prepared, missing, failed or merely declared unexecuted evidence cannot close this list.
- `requirement_resolution`: `resolved: true`, `authority_id` and nonempty `checks` mapping actual JSON pointers to expected values, including an actual successful completion status. This is an explicitly completed requirement authority, not the assembly plan.
- `status: "READY_FOR_FINAL_ASSEMBLY"`: set only after the finite manifest is complete and reviewed. This flag alone never bypasses evidence admission.

### Evidence records and projections

Each evidence row has `evidence_id`, `kind` (score/native/physical/paced/long/interpretation), `candidate_id`, `authority_id` (a root resource), `scope_label`, explicit `repetition`, and `status`. Unavailable statuses PREPARED, PARTIAL_OR_FAILED, PENDING_OR_UNVERIFIED and NOT_EXECUTED_WITH_EXPLICIT_FINAL_AUTHORITY require a reason and remain explicitly unavailable.

An AVAILABLE record needs `completion_checks`: a list of `{resource_id, equals: {"/status": "COMPLETE", ...}}`. Every checked resource must belong to the same authority DAG. Checks must include an actual positive completion status; a prepared/partial/unverified status cannot be admitted as completion. Different source schemas use their actual exact status strings.

AVAILABLE non-interpretation evidence also supplies `records`:

```json
{
  "resource_id": "coverage_csv_bound_by_core",
  "pointer": "",
  "where": {"/profile_id": "C065", "/stream": "O0", "/identity_tap": "O0"},
  "columns": {
    "candidate_id": "/profile_id",
    "asr_tap": "/stream",
    "identity_tap": "/identity_tap",
    "case_id": "/case_id",
    "status": "/status"
  }
}
```

For JSON, `pointer` names one actual list; for CSV it is empty. `where` selects exact fields; `columns` projects existing fields using JSON pointers relative to each row. There are no expressions, inline fabricated facts, arbitrary code, population unions, or implicit status conversions. Numeric/Boolean runtime fields must come from typed JSON metadata, not strings casually treated as true.

Actual runtime schemas may require a separately reviewed, source-bound normalized metadata receipt joining manifest, native result, closure and summary fields before this assembler can consume them. Such a receipt must retain every source binding and its identity checks. Missing fingerprints, terminal flags or unobserved fields must stay unresolved; do not invent them to satisfy the schema. This assembler checks the declared metadata proof, not raw trajectories or operating-system state.

For C conditions, copy exactly the registered `asr_tap`, `identity_tap`, `recipe_id`, `cue_condition`, `gallery_condition`, `enrollment_tier`, `profile_sha256` (canonical profile-object digest) and `executable_condition_sha256`. A byte hash of a formatted profile file is not interchangeable with that canonical digest. Historical conditions retain the exact `original_registration_row_sha256`, taps, NONE gallery and null tier.

Kind-specific rules:

- **Score:** actual candidate/tap/case/status rows. Full-bank means all 240 canonical cases successfully scored in one authority and one repetition. Failure rows remain in the declared denominator. Two panels cannot create a full-authority claim.
- **Native:** actual candidate/tap/case/status, `job_key` and `receipt_sha256`. Only COMPLETE and COMPLETE_REUSED are accepted native completion statuses. SCORED rejects even when a record carries native-shaped keys; score status never grants native integration. Completion and closure checks are separately required. COMPLETE_REUSED is retained as a row status, not converted to a new physical execution. Failed or unavailable native scopes remain explicit non-AVAILABLE evidence.
- **Physical:** actual inventory rows include `candidate_id`, `physical_id`, nullable `pid`, `creation_time`, `alive` and any explicitly projected original inventory classifications. IDs must be unique within the authority. Unknown owner/closure fields remain unknown. Required final physical evidence must have finite known creation and explicitly closed owners. Records are kept separately by authority; no cross-authority sum or conversion to model-call counts occurs. The old `physical_inference_count` cell remains blank.
- **Paced:** every actual cell supplies candidate/taps, cue/gallery/tier, `condition_sha256`, `status: "COMPLETE"`, `owner_closed: true`, `tail_complete: true`, `native_result_sha256`, positive `source_duration_sec`, canonical `case_id` and integer `repetition`. Supply `expected_grid` as exact [case_id, repetition] pairs from the bound manifest. Main qualification requires `scope_label: "MAIN_BALANCED_PACED"`, at least 12 first-repetition cases and at least four repeated cases from that same set. Diagnostic gate/sentinel/cross populations retain their own labels.
- **Long:** the same executed-condition/owner/tail/native fields, exactly one record with `continuous: true` and actual source duration from 1,800 through 3,600 seconds. Chronological cached replay or multiple short sessions do not substitute.
- **Interpretation:** a completed source authority plus explicit `text` and `limitations`; it is not transformed into score/native/runtime evidence.

Each retained operating preset must match both its completed main-paced and continuous evidence in candidate and every condition field. Scientific REPRESENTATIVE_EVALUATED also requires actual main-paced qualification. Other scientific dispositions retain their narrower meaning; a complete 240-row table does not imply every family is superior or fully evaluated.

## Run commands

Use the existing isolated interpreter. No Conda package installation is needed. The tests below are small, model-free fixtures. Template preparation and actual assembly are separate; obtain the exact completed metadata manifest before running assembly. Do not run real assembly during a paced quiet interval.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$report = "$sim\reports\S6C\20260910T123540Z"
$python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $python -B "$sim\scripts\s6c_final_disposition_v1.py" test
& $python -B "$sim\scripts\s6c_final_disposition_v1.py" template --plan "$report\candidate_disposition\FINAL_DISPOSITION_ASSEMBLY_PLAN_V2.json" --output "$report\candidate_disposition\FINAL_INPUT_TEMPLATE_V1.json"
# Fill and independently review a separate final input manifest; the template cannot complete.
& $python -B "$sim\scripts\s6c_final_disposition_v1.py" assemble --manifest "$report\candidate_disposition\FINAL_INPUTS_V1.json" --output-subdir final_candidate_disposition_v1
```

Anaconda Prompt / CMD:

```bat
set "JP_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "JP_REPORT=%JP_SIM%\reports\S6C\20260910T123540Z"
set "JP_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PYTHON%" -B "%JP_SIM%\scripts\s6c_final_disposition_v1.py" test
"%JP_PYTHON%" -B "%JP_SIM%\scripts\s6c_final_disposition_v1.py" template --plan "%JP_REPORT%\candidate_disposition\FINAL_DISPOSITION_ASSEMBLY_PLAN_V2.json" --output "%JP_REPORT%\candidate_disposition\FINAL_INPUT_TEMPLATE_V1.json"
rem Fill and independently review a separate final input manifest first.
"%JP_PYTHON%" -B "%JP_SIM%\scripts\s6c_final_disposition_v1.py" assemble --manifest "%JP_REPORT%\candidate_disposition\FINAL_INPUTS_V1.json" --output-subdir final_candidate_disposition_v1
```

## Outputs and limits

A fresh, contained final namespace receives `CANDIDATE_DISPOSITION_FINAL.csv`, `ORIGINAL_REGISTRATION_SNAPSHOT.csv`, `FINAL_ROUTE_EVIDENCE.json`, `OPERATING_PRESETS.json`, `FINAL_DISPOSITION.md` and `RECEIPT.json`. All admissions pass before any final output is written. A later filesystem write failure can leave a partial fresh directory; without the final receipt it is not complete. Existing output namespaces reject and original artifacts remain untouched.

The completion receipt says COMPLETE_EXPLICIT_DISPOSITION_ASSEMBLY and explicitly keeps `whole_study_complete: false`. It records exact input/source/code/README/output bindings. Independent final metadata and numerical review, any remaining runtime acceptance, and campaign acceptance remain separate. The 44 pure checks establish these parser/admission branches, not empirical candidate accuracy or completed real assembly.

The final normalized runtime joins still require the actual closed V7-generation receipts and their exact condition, native, observer and closure authority. Fields such as `condition_sha256` are normalized join outputs, not claimed to exist directly in every original record. Existing original records and earlier working snapshots do not become these final joins merely because the helper schema is ready. No actual final assembly has been run. The pre-native-status-fix source, README and 43-check receipt are preserved under `staging/s6c/20260910T123540Z/candidate_disposition/before_native_status_fix_v1`; the additional negative guard closes only the reported scoring/native status ambiguity.
