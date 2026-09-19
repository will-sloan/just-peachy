# Closed native176 scoring-input preparation

`s6d_native176_scoring_inputs_v1.py` prepares an executable input builder for the exact176-job native confirmation queue. It never runs the scorer, speech models, UI, hardware, a supervisor or another process. Existing source, results and reference populations remain immutable.

`prepare` reads only pinned static metadata/source files: prospective matrix ba965746, queue7cb1efcf, the source-parent and repaired manifests, scorer4260ba5d and its unchanged dependency tree, V4 runnerfdffb4ca, and original evaluator gallery maped136433. The frozen prospective scoring order and native execution order differ; each retains its exact original sequence and rows join uniquely by literal job ID. It verifies all176 memberships and176 comparison pairs, then writes a compact `PREPARED_ONLY_NOT_APPROVED` proposal under a fresh R directory. It does not inspect or poll live native state, claim owner exit, or create root approval.

`build` is a future operation requiring root's exact reviewed input JSON/hash. Before publishing any `APPROVED_CLOSED_NATIVE_INPUTS`, it requires exact FINISH/176 completed CHECKPOINT, matching immutable CLOSED_LOCK and SUPERVISOR_CLOSURE nonce paths, matching original supervisor launch PID/creation, keep-awake restoration, released ownership, closed successful payload census, and no active supervisor lock. Every saved job has exit0 and its exact run/job/child identity. Fresh read-only psutil PID+creation checks reject a still-present original instance; PID reuse is recorded separately and access denial/unknown identity blocks. No process is stopped or killed.

For each of176 jobs it reuses the **unchanged V4 `validate_completion` and `identity_matches` function ASTs** with a read-only binding cache. It compares the result with the saved validation; checks exact wrapper/native manifest/result/audit joins; hashes complete source WAV/PCM and both journal files; reuses the accepted bb1b completion/finalizer/consumer and full dispatch guards; checks reference source/frames and exact projected turns; and binds latest transcript and actual consumer events. No correctness calculation occurs. Source/reference bindings are checked once per unique file path, with stat identity checks at subsequent use and before commit. The consumer journal is parsed and hashed in one streaming pass. Source WAV header/PCM proofs derive from the same cached file read. The cache is only for this invocation and never licenses changed files.

The builder retains every original complete/incomplete/disallowed reference flag and opportunity. It emits all176 validated jobs, all176 original comparison pairs, and an empty `unavailable_jobs` list. A missing, active, failed, changed or unadmitted native input blocks the builder; it is never silently relabeled unavailable to finish early. Metric-level unavailable outcomes remain the frozen scorer's responsibility. The source-parent/repaired native consumer is headless; GUI render and scanout are not claimed.

Gallery rows are either the exact NONE object required by scorer4260 or the single matching row from the original completed SCORER_GALLERY_MAP, joined to the exact job gallery manifest. No new roster, profile mapping or person label is invented. All new materialized gallery rows and scoring inputs use a fresh G epoch. `SCORER_COMMAND_PROPOSED.json` contains the literal pinned analysis interpreter/scorer/`--spec`/`--sha256` command for separate root execution review. MeetEval0.4.3 is checked by the existing scorer when later executed; no package installation is performed.

## Input contract and outputs

`prepare --output FRESH_R_DIRECTORY` writes PROPOSAL.json. The future `build --admission ROOT_JSON --sha256 EXACT_SHA` JSON requires:

- schema `s6d-native176-scoring-build-admission.v1`; status `ROOT_ACCEPTED_NATIVE176_CLOSED_INPUT_BUILDER_V1`; `allow_closed_input_construction=true`.
- Exact bindings for `builder`, `readme`, `proposal`, actually used queue `approval`, `supervisor_launch`, FINISH `checkpoint`, matching `closed_lock`, and `supervisor_closure`. Each binding is `{path,bytes,sha256}`.
- `output_root`: fresh directory under `G:\Just_Peachy_S6D\20260913T195357Z`; `score_output_root`: fresh nested directory which the scorer will create later.

The approval must bind all176 unchanged job digests. The supervisor state directory is the exact original native176_state; no directory glob or latest-file selection is used. The builder also enforces current C50/G75 free-space floors. It creates no root input now. After successful future validation, outputs are exact gallery rows, VALIDATION.json with all176 completion bindings and observed process-absence evidence, SCORING_INPUTS.json, and a proposed scorer command. A failure before validation writes no approved scoring specification; fresh unused preparation fragments may remain if a later disk write fails. No old output is overwritten.

## Run in PowerShell / Anaconda PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$sim\scripts\s6d_native176_scoring_inputs_v1.py" prepare --output "$sim\reports\S6D\20260913T195357Z\application\native176_scoring_preparation_v1"
# Future, only after root reviews the builder and binds actual complete closure:
& $py -B "$sim\scripts\s6d_native176_scoring_inputs_v1.py" build --admission '<exact root admission.json>' --sha256 '<exact SHA256>'
```

## Run in Anaconda Prompt / CMD

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%SIM%\scripts\s6d_native176_scoring_inputs_v1.py" prepare --output "%SIM%\reports\S6D\20260913T195357Z\application\native176_scoring_preparation_v1"
rem Future only, after root reviews and binds completed closure:
"%PY%" -B "%SIM%\scripts\s6d_native176_scoring_inputs_v1.py" build --admission "<exact root admission.json>" --sha256 "<exact SHA256>"
```

After root separately admits the saved proposed scorer command, it uses `%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe -B <frozen4260scorer> --spec <SCORING_INPUTS.json> --sha256 <its hash>`. Do not substitute the live helper source or change pinned scorer semantics.

## Tiny fixtures

`s6d_native176_scoring_inputs_checks_v1.py --output FRESH_G_DIRECTORY` tests synthetic active/missing closure, keep-awake/census failures, PID reuse/access errors, exact cached file mutation handling, original gallery selection and accepted pure guard behavior. It does not call build on an approved admission, inspect active native state, check actual PID liveness or score actual/native text.

PowerShell: `& $py -B "$sim\scripts\s6d_native176_scoring_inputs_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native176_scoring_inputs_v1'`.

Anaconda/CMD: `"%PY%" -B "%SIM%\scripts\s6d_native176_scoring_inputs_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native176_scoring_inputs_v1"`.

Fixture outputs and preparation are not study completion or scoring approval. Use fresh suffixed paths for changed runs and preserve prior receipts.
