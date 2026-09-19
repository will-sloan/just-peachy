# S6C isolated epoch4 long native admission

`s6c_long_native_epoch4.py` admits one later continuous host session under an exact registered epoch4 profile. It reuses the original `s6c_long_session.py` native function without editing its source or body. It does not regenerate, trim, gain, copy, or recapture the existing 1,827.426625-second, 29,238,826-sample composition. The two prepared PCM16 files and shifted real cue file remain in the original epoch2 composition namespace.

The wrapper separates **source composition epoch2** from **actual native execution epoch4**. It verifies the reviewed epoch admission overlay, pinned manifests, every original APP module, native worker/common modules, model assets, interpreter and dependency versions. Epoch4 and epoch2 have identical APP/native/model semantics; the registered profile and gallery extension is admitted explicitly. The live long helper and prefix helper must resolve to their exact pinned files and to the admitted frozen epoch4 common module. There is no current/default APP fallback.

This README covers preparation and the later authorized run. `checks`, `source-checks`, and `prepare` do not construct models. The `run` action does construct one resident model bundle and runs one uninterrupted real-time paired-file session. Do not launch it concurrently with other model, HIL, or heavy analysis work. The task coordinator must first provide an exact quiet-period admission for the prepared manifest.

## Inputs and fixed boundaries

- Existing `reports/S6C/20260910T123540Z/long_session/v1/COMPOSITION.json`, SHA256 `bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3`, including exact audio, PCM and telemetry bindings.
- Pinned `EPOCH2_EXECUTION_MANIFEST.json` and `EPOCH4_EXECUTION_MANIFEST.json`, the reviewed `s6c_orchestrator_scan_v3.py` dependency chain, and original long/prefix/common source files. The frozen spec provides the actual model asset paths.
- One explicit candidate ID and ASR/identity tap pair present exactly once in the epoch4 registry. Taps are `O0` or `O1`. No historical B00/B01 substitution is supported here; those controls use their separate historical paced coordinator.
- Identity mode `none` with condition `NONE`, or `post_association` with the exact registered `FIXED_ROTATION_A` or `FIXED_ROTATION_B` and tier 5, 15 or 30. The wrapper resolves the one fixed, case-independent manifest automatically. It accepts no caller-supplied gallery, scene-derived roster, or common30 condition. Empty explicit galleries retain the APP's existing unknown-name fallback.
- Cue condition `CUES_OFF` or `REAL_ALIGNED_CUES` only. Scorer case/person annotations from the composition are not passed as predictor inputs.
- A fresh output namespace beginning `epoch4_`, an explicit UTC deadline, and (for real execution only) a coordinator-created quiet admission JSON. The global no-new-work deadline is 2026-09-13 11:35:40 UTC, preserving the final closure hour.

Preparation binds this helper and README. After a manifest is prepared, do not edit either file before its run; prepare a new source/versioned admission if a reviewed fix is needed. Existing plans and native attempt directories are never overwritten or resumed. A failed native attempt needs a new namespace and a new reviewed admission; it is a separate physical session.

## PowerShell

Use the existing native environment; no installation or activation is needed:

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_long_native_epoch4.py'
& $s6cPython $s6cScript checks
```

The one-time source admission below verifies the existing large source/model bindings but performs no model call. It creates an immutable receipt and should not be repeated into the same receipt after completion:

```powershell
& $s6cPython $s6cScript source-checks
```

After the task coordinator supplies a selected candidate and route, replace the example values below with that exact authorized selection. `C001` is a command-shape example, not a recommendation or selected long result. Choose a fresh namespace:

```powershell
& $s6cPython $s6cScript prepare --namespace epoch4_example_c001_o0 --candidate C001 --asr-tap O0 --identity-tap O0 --deadline-utc '2026-09-13T11:35:40Z'
```

The later execution command requires the coordinator's actual quiet-admission path:

```powershell
$s6cManifest = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\long_native_epoch4\epoch4_example_c001_o0\MANIFEST.json'
$s6cQuietAdmission = 'C:\replace-with-coordinator-approved-path\QUIET_ADMISSION.json'
& $s6cPython $s6cScript run --manifest $s6cManifest --quiet-admission $s6cQuietAdmission
```

## Anaconda Prompt or Windows CMD

The exact native Python executable is called directly, even if an Anaconda environment is already activated:

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SCRIPT=%S6C_SIM%\scripts\s6c_long_native_epoch4.py"
"%S6C_PYTHON%" "%S6C_SCRIPT%" checks
"%S6C_PYTHON%" "%S6C_SCRIPT%" source-checks
```

For the coordinator-selected preparation and later authorized execution:

```bat
"%S6C_PYTHON%" "%S6C_SCRIPT%" prepare --namespace epoch4_example_c001_o0 --candidate C001 --asr-tap O0 --identity-tap O0 --deadline-utc "2026-09-13T11:35:40Z"
set "S6C_MANIFEST=%S6C_SIM%\reports\S6C\20260910T123540Z\long_native_epoch4\epoch4_example_c001_o0\MANIFEST.json"
set "S6C_QUIET_ADMISSION=C:\replace-with-coordinator-approved-path\QUIET_ADMISSION.json"
"%S6C_PYTHON%" "%S6C_SCRIPT%" run --manifest "%S6C_MANIFEST%" --quiet-admission "%S6C_QUIET_ADMISSION%"
```

Do not treat the example quiet-admission filename as permission to launch. Its content must have status `AUTHORIZED_FOR_QUIET_LONG_NATIVE`, the exact prepared manifest SHA256, `all_other_model_hil_work_stopped: true`, `all_heavy_analysis_stopped: true`, and an aware `expires_utc` with enough time for the entire source plus the configured drain and closure allowance. The same PID/creation owner must hold the shared `PACED_QUIET_OWNER.json` lease. The wrapper never deletes a prior lease or stop request.

## Outputs and provenance

`source-checks` writes `REPORT/long_native_epoch4/SOURCE_CHECKS_V2.json`. It preserves the earlier V1 receipt and binds the exact pre-review helper/README snapshots in `STAGING/long_native_epoch4/pre_review_repairs_v1`. The later admission closes two prospective guards: exact-buffer authority reads and release-outcome ordering. The old admission is not represented as having executed the corrected helper. `prepare` writes `REPORT/long_native_epoch4/<namespace>/MANIFEST.json` with complete source, original composition, actual epoch4 spec, registered profile, gallery and resource bindings.

`run` creates a unique `invocations/<id>/ADMISSION.json`, resource heartbeat, pre-release `NATIVE_OUTCOME.json` and final `CLOSURE.json` beside the prepared manifest. Native reports go under `REPORT/long_session/<namespace>/native/<candidate>/<ASR>_<ID>/<condition>/`; native session payloads go under `G:\Just_Peachy_S6C\20260910T123540Z\long_session/<namespace>/native/...`. The original native worker writes `STARTED.json`, process sample JSONL, and `RESULT.json` or `FAILURE.json`; native sessions retain their normal full journals, event/transcript outputs and finalization receipt.

The wrapper parses and hashes the same exact byte buffer for the prepared manifest, quiet admission and final native result. It retains the admitted manifest binding through execution and rechecks its on-disk bytes immediately before calling native. The wrapper binds, but never rewrites, the native `RESULT.json`. That result's `composition` points to epoch2 source preparation. The outer ADMISSION/CLOSURE are the authority for **actual execution epoch4**, with the exact profile/spec and result binding. An execution collector must resolve this outer lineage instead of using the composition epoch as the execution epoch. Native completion and process exit are distinct: `NATIVE_COMPLETE_QUIET_LEASE_RELEASED` is written only after successful lease rename and archive-byte verification; an external PID/creation check is still needed to certify that the current Python process has exited. A rename failure leaves a durable native outcome and a final failed/unverified release status, with the existing lease retained. A successful rename followed by an archive-read failure is explicitly released-but-binding-unverified, not silently treated as fully verified.

## Resource, stop and observation scope

One worker and one inner thread are used. Admission enforces the shared S6C floors of 50 GiB free on C:, 75 GiB on G:, 12 GiB available RAM, and 120 GiB maximum new REPORT/STAGING/PAYLOAD storage. It additionally reserves 4 GiB of pending output headroom on admission and caps this invocation at two hours. Other observed study worker/coordinator commands and recorded epoch workers must be closed; inaccessible recorded owners fail closed. This is a checked study-owner inventory plus the coordinator's quiet declaration, not a complete audit of unrelated OS activity.

Resource checks occur at admission, approximately every two seconds when the original native sampling loop executes, and at terminal closure. Full metadata-only storage/owner scans occur at most every 20 seconds. These scans add host overhead and may cause irregular observation gaps. Synchronous model admission and the original bounded finalization join do not invoke the sampling hook, so they are **not continuously resource-guarded**. The original worker's bounded drain/stop logic remains intact. `REPORT/STOP_REQUEST.json` stops admission and is checked in the running session; a triggered guard raises into the original worker's owned stop/failure path. Persistent I/O or lease-release failure remains visible and blocks another quiet run until an explicit closure/resolver is supplied.

Only `load_composition`, `admit_work`, and `process_sample` are overridden inside the temporary wrapper context. The original native function and selected supporting function identities/code are checked before, during and after this context; all three overrides are restored even when native execution fails. No APP/model/decoding/identity/scheduler method is patched.

The input concatenates 38 independently reset physical captures with declared inserted digital silence; it does not establish uninterrupted hidden XVF hardware state. This is a continuous host-session endurance check. Sampled backlog/memory maxima are observed-sample maxima, missing measurements remain unavailable, and no CM5, phonetic latency, GUI, or continuous HIL claim follows from this runner. Model-free fixtures prove only their named admission/guard branches; actual long-session completion requires later native receipts.
