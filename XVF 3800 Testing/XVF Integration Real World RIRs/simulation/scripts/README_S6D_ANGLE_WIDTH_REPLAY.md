# S6D bounded operational tracker-width preparation and replay

Purpose: prepare and, only after coordinator admission, replay the exact approved operational-width neighborhood using the preserved S6C epoch 4 incremental policy implementation and its original epoch 2 N01 neural evidence. This is separate from the evaluator-only manual-label 5/2/0 rescore. It does not estimate physical sensor noise.

The only changed numerical field is `tracker.direction_match_deg`: 2, 5, 10 or 20 degrees, from the complete C079 normalized-joint and C120 reliability-joint parents. Profile labels receive an S6D namespace. The inactive endpoint `xvf.direction_match_deg` stays at 25 degrees, all other scalar weights/settings remain unchanged, and the original manual-label uncertainty stays at 5 degrees. The field controls both observed-bearing likelihood scale and inherited spatial consistency behavior, so the study is operational width sensitivity, not a pure Gaussian-noise experiment.

There are eight new policy conditions, sixteen explicit jobs (each one parent/width/tap), and 3,840 cells over all 240 scenes and both same-tap O0/O1 routes. Existing C079/C120 25-degree real-cue predictions and C065/C119 cue-off predictions are retained as exact controls. Existing C147–C154 provide three shuffled seeds and nominal diagnostic context at 25 degrees. No new null grid, new waveform, new neural run, gallery or training is created.

## Inputs and outputs

`prepare` takes a **fresh** S6D report directory and a new policy-payload directory under `G:\Just_Peachy_S6D`. It reads the original full N01 anonymous prediction index and policy plan through their core-analysis receipt, original epoch 4/2 manifests and effective profiles, original native source index/receipts, the complete parent/control prediction bytes, original real telemetry, and per-cell existing score metadata. It verifies application graph equality and conservative neural dependency equality without importing application/model modules or loading neural payload arrays.

Preparation outputs sixteen profile JSON files, `PLAN.json` with all 3,840 literal cells and their exact source/output paths, 1,920 existing parent/off control bindings, 480 unique native source receipts, population counts and `REUSED_DIAGNOSTICS.json`. The model assets are declarations from the original frozen manifests, not newly loaded or modified weights. Native evidence/vector/event/journal bytes are reverified by the original `load_evidence` only during separately admitted execution. Prediction/receipt metadata verification is not a fresh neural run.

`execute` requires the exact prepared plan, a coordinator authorization JSON, and a literal list of predeclared job IDs. The authorization has `root_review_passed: true`, the exact `plan_sha256`, and `allowed_jobs` containing each admitted job. There is no implicit `all` or candidate search. It imports only the original frozen epoch 4 policy helper/API; it never invokes a neural extraction worker or device owner. It validates profiles with the actual API when execution begins. Every cell uses the original native evidence, observed-only provider and anonymous gallery-disabled policy.

Execution outputs immutable gzip predictions to the predeclared new payload locations, per-cell receipts, an admission receipt and a new `PREDICTION_INDEX.json` under the preparation directory's `executions` child. All three final-text views must equal the exact parent word sequences. It preserves all assignments, Unknown states, returns and failures for subsequent scoring. It does not claim that scoring, physical capture, native confirmation or S6D is complete. Existing targets are rejected; interrupted or failed runs require coordinator diagnosis and a new reviewed output epoch rather than unbound reuse.

Keep complete nonempty (203 scenes/6,016 reference words), primary (156 scenes/4,560 words), complete-overlap (47 scenes/1,456 words), incomplete (26 scenes), and empty (11 scenes) denominators separate. Prepared population counts are derived from existing controls. A retained behavior change requires the declared native/source-paced confirmation and the relevant naming/display evidence before recommendation.

## Metadata-only preparation

Use the existing Edge Python 3.11 environment; no installation is required. The physical Anaconda 3.12/vendor stack is not used for this policy study.

PowerShell:

```powershell
$s6dRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6dSim = "$s6dRepo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$s6dReport = "$s6dSim\reports\S6D\20260913T195357Z"
& "$s6dRepo\.edge-speech-env\python.exe" -B "$s6dSim\scripts\s6d_angle_width_replay.py" prepare --output "$s6dReport\angles\operational_width_v1" --payload-root 'G:\Just_Peachy_S6D\20260913T195357Z\operational_width_v1'
```

Anaconda Prompt / Windows CMD:

```bat
set "S6D_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6D_SIM=%S6D_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6D_REPORT=%S6D_SIM%\reports\S6D\20260913T195357Z"
"%S6D_REPO%\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_angle_width_replay.py" prepare --output "%S6D_REPORT%\angles\operational_width_v1" --payload-root "G:\Just_Peachy_S6D\20260913T195357Z\operational_width_v1"
```

Expected final status: `PREDECLARED_METADATA_ONLY_NOT_EXECUTED`, sixteen jobs, 3,840 cells, 480 native sources, zero new neural/hardware jobs. Preparation writes only metadata. Use a new revision name if an output directory already exists.

## Coordinator-admitted policy replay

This command is documented for later root admission. It was not executed during preparation. Example authorization for one job:

```json
{"root_review_passed":true,"plan_sha256":"ACTUAL_REVIEWED_PLAN_HASH","allowed_jobs":["S6D_C079_W02_O0"]}
```

PowerShell:

```powershell
& "$s6dRepo\.edge-speech-env\python.exe" -B "$s6dSim\scripts\s6d_angle_width_replay.py" execute --plan "$s6dReport\angles\operational_width_v1\PLAN.json" --authorization "$s6dReport\angles\operational_width_v1\ROOT_JOB_ADMISSION.json" --jobs S6D_C079_W02_O0
```

Anaconda Prompt / CMD:

```bat
"%S6D_REPO%\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_angle_width_replay.py" execute --plan "%S6D_REPORT%\angles\operational_width_v1\PLAN.json" --authorization "%S6D_REPORT%\angles\operational_width_v1\ROOT_JOB_ADMISSION.json" --jobs S6D_C079_W02_O0
```

Job IDs are exactly `S6D_<C079 or C120>_W<02,05,10,20>_<O0 or O1>`. Each contains 240 scenes. Multiple literal jobs may be supplied only if each appears in the coordinator's authorization. No source/reference identities, manual angle interval or true source schedule is provided to `run_policy`; case IDs are filesystem/provenance labels. Neural words are fixed by the cache, and raw-word parity is checked against the frozen parent on every executed cell.
