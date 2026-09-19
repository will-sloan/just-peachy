# S6C canonical paired paced candidate adapter

`s6c_paced_epoch4.py` prepares and later coordinates source-paced candidate cells through the unchanged `s6c_long_session.py` native function and its real in-process telemetry/process observer. It supplies one exact canonical source pair per cell, rather than the separate 30-minute composition. It does not copy audio, generate a new waveform, add silence, shift timestamps, crop, or apply gain. The exact indexed processed-view length is used; a 45-second acoustic scene label is not substituted for its shorter captured/prepared view.

Each selected candidate receives the fixed metadata panel's 16 cases and four additional repeated cases, both registered ASR-tap routes: 40 cells per candidate. Each cell gets a fresh Python process, resident model bundle, session, anonymous/naming state and gallery load. The second repetition reverses candidate order. Final candidate IDs are deliberately not hard-coded or selected by this helper. No general accuracy or finalist claim follows from preparation or these runtime cells.

The default `--panel-mode full16_plus4` keeps that panel. The separate `--panel-mode gate6_diagnostic` admits only the original registered `C071,C082` profiles, in that order, on the proposal's exact six `family_native_gate_case_ids`: S45_02_10, S45_03_03, S45_04_07, S45_05_05, S45_06_19 and S45_12_11. Both ASR taps and one repetition produce 24 cells, or 1,072.6905 seconds (17.878175 minutes) of actual source audio across cells. This diagnostic examines pacing effects on released tracker context/debt, active-speech-conditioned context and full cost/quality. It does not promise to rescue source-span-deterministic cue-event triggers, change a profile, or select finalists.

The native body is preserved byte-for-byte. Temporary overrides are limited to its composition loader (returning a **canonical single-scene source record**), resource admission, and the existing process-sampling hook. Native model, frontend, ASR, tracking, gallery, scheduler and export methods are not patched. The actual epoch4 APP/worker/common/assets/interpreter are admitted through the same pinned epoch2/4 compatibility overlay used by the reviewed long wrapper. No model is created by `checks`, `source-checks`, or `prepare`.

## Inputs

- Exact `EPOCH4_EXECUTION_MANIFEST.json`, reviewed immutable native code/assets, and the existing native `.edge-speech-env` Python.
- `design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json`, SHA256 `f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da`: 16 cases/all 12 families, two taps, and four explicit sensitive repeats. The helper uses the case list and repeat list; evaluator gallery/person annotations in the panel do not enter runtime.
- Canonical input index, full mono PCM16 O0/O1 waveform/hash/frame bindings, and the unchanged corresponding sanitized telemetry. O0 already contains its original +3 dB; input adapter gain remains one. O1 remains unity. Both lanes start at the same source sample zero. Added offset and inserted gap are exactly zero; the 50 ms RIR convention is not added again.
- Explicit selected candidate IDs, each with exactly one registered identity route per ASR tap. Only no gallery or exact fixed `FIXED_ROTATION_A/B` galleries at the registered tier are supported. Scene-derived, common30 and larger-roster conditions are rejected rather than substituted. Cue routes are real aligned packets or cues off only.
- A fresh output namespace and a bounded UTC deadline. Actual run additionally requires a coordinator-created quiet admission matching the exact manifest hash, with status `AUTHORIZED_FOR_QUIET_PACED`, `all_other_model_hil_work_stopped: true`, `all_heavy_analysis_stopped: true`, and a sufficient aware `expires_utc`.

## PowerShell

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_paced_epoch4.py'
& $s6cPython $s6cScript checks
```

The one-time source check reads and verifies the existing 32 complete canonical PCM views and source/asset bindings without inference, then writes an immutable source receipt:

```powershell
& $s6cPython $s6cScript source-checks
```

After final candidate selection, substitute the coordinator's exact comma-separated IDs and a fresh namespace. `C001` below illustrates command syntax; it is not a selected finalist:

```powershell
& $s6cPython $s6cScript prepare --namespace selected_panel_v1 --candidates C001 --deadline-utc '2026-09-13T11:35:40Z'
$s6cManifest = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\paced_candidates\selected_panel_v1\MANIFEST.json'
$s6cQuiet = 'C:\replace-with-approved-path\QUIET_ADMISSION.json'
& $s6cPython $s6cScript run --manifest $s6cManifest --quiet-admission $s6cQuiet
```

Do not run the last command until the actual quiet admission exists and other model/HIL/heavy analysis workers have closed. The `worker` action is internal: the coordinator supplies a live parent-owned quiet lease, exact manifest and cell ID. It is not a standalone user inference command.

The separately reviewed six-case diagnostic can be prepared without starting any models:

```powershell
& $s6cPython $s6cScript prepare --namespace gate6_c071_c082_v1 --panel-mode gate6_diagnostic --candidates C071,C082 --deadline-utc '2026-09-13T11:35:40Z'
```

Its manifest is `reports\S6C\20260910T123540Z\paced_candidates\gate6_c071_c082_v1\MANIFEST.json`. Use that exact path and its own subsequent quiet admission for a later authorized run. Preparation itself is not quiet-run authorization.

## Anaconda Prompt or Windows CMD

Call the exact native Python directly; no package installation is required:

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SCRIPT=%S6C_SIM%\scripts\s6c_paced_epoch4.py"
"%S6C_PYTHON%" "%S6C_SCRIPT%" checks
"%S6C_PYTHON%" "%S6C_SCRIPT%" source-checks
"%S6C_PYTHON%" "%S6C_SCRIPT%" prepare --namespace gate6_c071_c082_v1 --panel-mode gate6_diagnostic --candidates C071,C082 --deadline-utc "2026-09-13T11:35:40Z"
```

For the later exact selected candidate list and authorized quiet period:

```bat
"%S6C_PYTHON%" "%S6C_SCRIPT%" prepare --namespace selected_panel_v1 --candidates C001 --deadline-utc "2026-09-13T11:35:40Z"
set "S6C_MANIFEST=%S6C_SIM%\reports\S6C\20260910T123540Z\paced_candidates\selected_panel_v1\MANIFEST.json"
set "S6C_QUIET=C:\replace-with-approved-path\QUIET_ADMISSION.json"
"%S6C_PYTHON%" "%S6C_SCRIPT%" run --manifest "%S6C_MANIFEST%" --quiet-admission "%S6C_QUIET%"
```

`source-checks` is a one-time immutable receipt operation. Repeat `checks` freely, but use a separately reviewed version if the held source changes after source admission or candidate preparation. Existing complete cells are re-admitted only from exact per-cell receipt/artifact bindings and closed owned PID/creation identities; this is a resumed reference, not new paced inference. A failed/incomplete cell is preserved and requires a separately diagnosed new namespace.

Completion reuse checks the original bound cell, native result, child launch/admission/outcome, exact job/source/profile/epoch/gallery, full paired journals, session finalization, artifact membership and all recorded owner identities. Deterministic measurement fields and sampled phase observations are recomputed from that same native evidence. Original coordinator `completed_cell_wall_sec` is retained from the immutable completion receipt after positive-finite validation; it is not reconstructed from nested clocks. The original completion binding remains in the resumed index. Reuse currently requires the exact same manifest and namespace. Diagnostic cells are scientifically identical to matching first-repetition cells of a later unchanged full panel, but cross-manifest reuse requires a separate explicit re-admission adapter; this helper does not silently transfer them.

## Outputs and source interpretation

`REPORT/paced_candidates/SOURCE_CHECKS_V3.json` binds the current no-model source check, complete-chain/lease fixes and gate6 mode. V2's receipt remains unchanged; its exact helper/README are preserved under `STAGING/paced_candidates/pre_reuse_and_gate6_v2` and resolved explicitly by V3. V1 remains preserved under `STAGING/paced_candidates/pre_progress_v1` through V2. Preparation creates `REPORT/paced_candidates/<namespace>/MANIFEST.json` and 16 small per-case source JSON files for the full panel, or six for the diagnostic. There are no new audio inputs. Reports for each fresh cell are under `.../jobs/<job_id>`; actual native session payloads are under `G:\Just_Peachy_S6C\20260910T123540Z\paced_candidates/<namespace>/jobs/<job_id>`.

Each cell preserves `LAUNCH.json`, `WORKER_LOG.txt`, outer `PROCESS_TREE_SAMPLES.jsonl`, `CELL_ADMISSION.json`, `CELL_OUTCOME.json`, `CELL_RESULT.json`, and the unchanged native helper's `STARTED`, `RESULT` or `FAILURE`, process samples and actual session artifacts. The native body writes complete paired PCM journals, model/embedding/segmentation events, ASR words, anonymous/name/revision exports and finalization evidence. The coordinator publishes `COMPLETE.json` only after exact cell-result identity and observed owned-process closure checks. `PACED_INDEX.json` lists complete or exactly reused cell receipts. Invocation OUTCOME/CLOSURE records preserve partial failures, lease release and owner identities.

The original native RESULT's field named `composition` binds the **canonical single-scene source JSON** here. Its fixed prose about concatenated captures is a generic inherited string, not the actual source description. `CELL_RESULT.json` explicitly supplies `source_kind: CANONICAL_SINGLE_SCENE_PAIR`, actual epoch4, zero source offset and zero inserted gap. It does not claim the epoch2 long composition, 30-minute endurance, or continuous hidden XVF state. A later inventory must use this per-case schema and distinct branch; it must not infer long-session execution from the inherited helper/result names. Original durable results are never rewritten to hide this distinction.

## Runtime and resource scope

One quiet coordinator launches one fresh child at a time with one inner thread. The shared `PACED_QUIET_OWNER.json` lease excludes historical controls and long sessions. Common reserves remain 50 GiB on C:, 75 GiB on G:, 12 GiB available RAM and a 120 GiB new-output cap, with 512 MiB pending-cell headroom. Resource metadata is checked before cells and every 20 seconds; available RAM/free disk are checked on every outer sample. Eight hours is the invocation limit, and each cell has its explicit bounded drain/time allowance. The stage deadline retains one closure hour. `REPORT/STOP_REQUEST.json` stops admission and active work. Cleanup targets only recorded owned PID/creation identities; no unrelated process is terminated.

After failure cleanup, the coordinator rechecks every recorded owned child. A live child or an unavailable inspection produces `LEASE_RETAINED_OWNED_CLOSURE_UNVERIFIED`; the quiet lease remains in place and blocks later admission until explicitly resolved. Cleanup failures and null inspection states remain in the outcome. Lease archival/release is attempted only after every recorded owned identity is confirmed closed. This does not prove unrecorded descendants never existed.

The outer observer samples the real child process tree approximately every 0.5 seconds, including model startup, and records coordinator RSS separately. The original in-process observer samples actual source/ASR/speaker cursors, backlog, state, event counts and process resources approximately every two seconds plus after finalization. It also drains the application event queue through the original code. No active JSON status polling or missing-LIVE substitution is needed. Process inspection errors stay visible and unavailable totals stay null. Full metadata scans and OS scheduling can create gaps; neither series proves continuous maxima. Native display-event timestamps remain separate from sampled queues and modeled replay times.

Heartbeat `measured_progress` uses actual completed source seconds, completed cell wall time, nested model-startup/native intervals and explicit sampled completion phases. Before any completion, rates/means/ETA are null. Reused completed cells may inform the heuristic ETA, but their source seconds are excluded from current-invocation throughput. ETA uses the same candidate/tap's observed cell wall when available, otherwise the pooled completed cells, subtracting active elapsed time with a 10% residual floor while the cell remains active; the displayed 0.75–1.5 range is heuristic, not a confidence interval.

The native source does not timestamp exact EOF, so `exact_eof_drain_sec` remains null. Closed process samples bound the interval from full-source-cursor publication to the terminal post-finalization observation using the last non-full and first full cursor samples. This interval includes final block pacing and closure; it is not an exact ASR drain, phonetic latency, replay estimate or inference-call equivalent. Actual cell wall includes fresh process admission/model/file/drain/closure and parent verification. Its nested startup/native/phase timings must not be added to that wall measurement. Every completed measurement remains source-bound in its cell receipt.

This is actual host source-paced integration when it later runs. A producer publishes each block before its sleep; wall time minus source cursor is not phonetic latency. Desktop CPU/memory do not qualify the 2 GB CM5 target. Panel correctness still requires comparison with the full-bank results and actual adverse cases; model-free fixtures establish only their stated guards. No native cell or candidate is claimed executed by the current source preparation.
