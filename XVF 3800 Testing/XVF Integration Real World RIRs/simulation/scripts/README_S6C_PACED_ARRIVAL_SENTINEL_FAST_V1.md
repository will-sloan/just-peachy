# Prospective exact-stat observer version

This separate version preserves the original scientific routes, waveform inputs, model/native functions, score definitions, and output schema/directory family. Every actual namespace must end in _fast_v1; old sources and prepared manifests stay unchanged. Commands below use the new wrapper.

The canonical fast helper installs only the loaded frozen common module's tree_bytes observer. Each nondirectory size uses fresh os.stat, avoiding stale Windows directory-entry sizes after hardlink growth. Traversal/access/unsupported reparse failures are explicit. Periodic full scans start at least 20 seconds after the preceding scan completes; all mandatory full checks, cheap checks, limits, timeout and headroom remain. About 40 seconds per full scan was measured: resource samples are irregular and add host overhead. observer_policy is required in each new manifest. Separate observer_fast_v1/attempts exit receipts record exact wrapper/owner/manifest, scanner timings, errors and restoration; these do not establish native/process closure.

Preparation validates inputs and writes JSON metadata only. Run consumes the exact manifest plus an agent-generated quiet admission after all other native/heavy work has closed. Do not infer runtime success from preparation or source checks. See the canonical fast helper README and shared observer README for detailed policy and restoration behavior. The inherited instructions below describe purpose, inputs, outputs, PowerShell and Anaconda/Command Prompt invocations; previously cited original-source receipts remain historical evidence, not new-wrapper execution.

# S6C exploratory paced arrival sentinel

Purpose: prepare and later run exactly S45_08_07 with original C088/C105 fixed rotation A,15-second gallery, both O0/O1 same-tap routes and three repetitions:12 cells,536.34525 seconds of source audio. This one-case diagnostic was selected after an observed native/cache arrival-boundary discrepancy. It is exploratory, not an independent test, a finalist selection, or a replacement for the main16+4 panel or C071/C082 gate6. Every repetition is retained.

`s6c_paced_arrival_sentinel_fast_v1.py` is an additive adapter derived from the exact reviewed `s6c_paced_epoch4.py` SHA256 b4b0dc48190654edbdcb6259cf2b8abc08d8675d49367863ff539f7eb54df8a3. The held adapter, its sources/manifests, the epoch4 APP/native worker, weights, galleries and registry are unchanged. Runtime uses the same original `s6c_long_session.native` function with one canonical source pair and its original event/process observer. No DSP, inference, tracker, naming or scientific output algorithm is patched; the resource-observer cadence change is stated above.

Inputs are the immutable epoch4 manifest and assets, exact canonical input index/PCM/telemetry, and `design/PACED_ARRIVAL_SENTINEL_SELECTION_V1.json` SHA25613490a4773b5be366b6a7d7e47013f8cd3ab9a8d34a3f9d99f33c539a24f2d4b. The profile guard allows only profile ID, tracker.cues_enabled false to true and xvf.mode none to tracking_only to differ between C088/C105. Both use the same actual FIXED_ROTATION_A tier15 gallery; endpoint, ASR, source support, model and naming settings must match. No new candidate or threshold is introduced.

Each cell uses the complete original44.6954375-second,715127-frame mono16kHz PCM view with zero source offset and zero inserted gap. O0's existing+3dB is not repeated; both adapters consume unity. No audio is copied or generated. Each later cell gets a fresh process/session/model bundle/gallery load. Candidate order is C088,C105 in repetitions1/3 and reversed in repetition2. Repetition IDs are separate, not independent people or scenes.

The adapter has a distinct manifest schema `s6c-paced-arrival-sentinel.v1`, cell schema `s6c-paced-arrival-sentinel-cell-result.v1`, quiet lease kind and REPORT/PAYLOAD `paced_arrival_sentinel/<namespace>` roots. Source_kind remains CANONICAL_SINGLE_SCENE_PAIR. The generic unchanged native RESULT still calls its source field composition; the explicit sentinel cell receipt gives the actual single-scene semantics. Never describe this as a long session or uninterrupted device capture.

PowerShell (no installation or Anaconda environment mutation):

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cSentinel = Join-Path $s6cSim 'scripts\s6c_paced_arrival_sentinel_fast_v1.py'
& $s6cPython $s6cSentinel checks
& $s6cPython $s6cSentinel source-checks
```

`checks` runs pure guards plus the inherited original guard fixtures. `source-checks` performs exact immutable source/profile/gallery/PCM admission for the two existing views and writes `REPORT/paced_arrival_sentinel/observer_fast_v1/SOURCE_CHECKS_V1.json`. Neither creates a model or starts inference. Source-checks is an immutable one-time operation; preserve its output and use a separately reviewed version for changes.

Only after independent source review and explicit coordinator preparation approval:

```powershell
& $s6cPython $s6cSentinel prepare --namespace arrival_boundary_fast_v1 --candidates C088,C105 --deadline-utc '2026-09-13T11:35:40Z'
```

Outputs are `REPORT/paced_arrival_sentinel/arrival_boundary_fast_v1/MANIFEST.json` and one small source JSON, with payloads later under `G:\Just_Peachy_S6C\20260910T123540Z\paced_arrival_sentinel\arrival_boundary_fast_v1`. Preparation does not authorize native execution.

For a later separately authorized quiet interval only:

```powershell
$s6cManifest = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\paced_arrival_sentinel\arrival_boundary_fast_v1\MANIFEST.json'
$s6cQuiet = 'C:\replace-with-approved-path\QUIET_ADMISSION.json'
& $s6cPython $s6cSentinel run --manifest $s6cManifest --quiet-admission $s6cQuiet
```

Anaconda Prompt / Windows CMD equivalents:

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SENTINEL=%S6C_SIM%\scripts\s6c_paced_arrival_sentinel_fast_v1.py"
"%S6C_PYTHON%" "%S6C_SENTINEL%" checks
"%S6C_PYTHON%" "%S6C_SENTINEL%" source-checks
"%S6C_PYTHON%" "%S6C_SENTINEL%" prepare --namespace arrival_boundary_fast_v1 --candidates C088,C105 --deadline-utc "2026-09-13T11:35:40Z"
set "S6C_MANIFEST=%S6C_SIM%\reports\S6C\20260910T123540Z\paced_arrival_sentinel\arrival_boundary_fast_v1\MANIFEST.json"
set "S6C_QUIET=C:\replace-with-approved-path\QUIET_ADMISSION.json"
"%S6C_PYTHON%" "%S6C_SENTINEL%" run --manifest "%S6C_MANIFEST%" --quiet-admission "%S6C_QUIET%"
```

Run requires a fresh exact-manifest quiet admission: AUTHORIZED_FOR_QUIET_PACED, all_other_model_hil_work_stopped true, all_heavy_analysis_stopped true, and an aware sufficient expires_utc. The shared PACED_QUIET_OWNER.json excludes other historical/candidate/long native work. One quiet owner launches one child at a time, inner threads1. The internal worker command requires its live owner lease and is not a standalone launch route.

Inherited reserves are C50GiB, G75GiB, availableRAM12GiB, new-output cap120GiB and512MiB pending-cell headroom. Existing STOP_REQUEST.json, full metadata guards with 20 seconds between completion and next start, sampled RAM/free-space checks,8-hour invocation bound and stage closure hour remain. Only recorded owned processes are cleaned up; unknown/live closure retains the quiet lease. Failures and incomplete namespaces are preserved and require explicit diagnosis before a new namespace. Exact completed cells can be re-admitted only within their original manifest/namespace; they are cache references, not new paced executions.

Actual outputs include per-cell LAUNCH, CELL_ADMISSION, CELL_RESULT/CELL_OUTCOME, native RESULT and original journals/events/finalization, PROCESS_TREE_SAMPLES, immutable COMPLETE, invocation OUTCOME/CLOSURE and final PACED_INDEX. Resource peaks are observed samples, not continuous maxima. Coordinator wall includes child startup/admission/model/run/drain/closure/verification; nested times must not be added again. Actual emitted words/names/labels/revisions and source cursors must be compared after closure. Publishing a block before sleep does not establish negative phonetic latency. No CM5, hardware freshness or broad accuracy claim follows from this diagnostic.
