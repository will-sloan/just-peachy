# S6C closed continuous native diagnostics V1

`s6c_long_diagnostics_v1.py` reads already closed, admitted C-candidate continuous host sessions. It creates direct observations of native execution, with no models, policy replay, transcript correction, reference alignment or canonical-scene/name scorer. The code and this README are a separately bound report helper; original native execution, inventories and converters remain unchanged.

## Purpose and accepted scope

The input must be the reviewed epoch4 continuous wrapper chain, with source composition from epoch2: 38 whole pieces, 29,238,826 frames at 16 kHz, 1,827.426625 seconds, including 74 seconds of added silence. Composition SHA-256 is `bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3`. Exact registered profile, fixed A/B roster or explicit NONE, source routes, native epoch, owner and released quiet lease are admitted through the pinned inventory V3 `validate_outer` function. The owner's recorded PID and creation time must currently be confirmed closed.

This is one uninterrupted host pipeline over captures whose physical XVF acquisition and source-cue histories were reset between pieces. It is not a continuous physical XVF/CM5 capture. The helper does not put the concatenation through a canonical scene API, create a composite reference, or compute WER, correctness, exposure or enrolled-person accuracy.

Inventory V5 remains the accounting adapter for the separate canonical/sentinel/B36 branches. This helper uses its unchanged inventory V3 dependency for C-epoch4 continuous admission and does not admit B36 or paced single-scene cells as long sessions.

## Inputs and verification

Supply one or more explicit `ADMISSION.json` paths and their SHA-256 values from completed `long_native_epoch4/<namespace>/invocations/<invocation>/` directories. Preparation verifies the complete metadata chain and preserves the exact parsed metadata buffers. It checks the original native result, paired journal declarations, finalization, native summary profile and final telemetry. Both paired journal lengths/hashes must equal the admitted composition; this helper does **not** read PCM or rehash model assets. The original native worker did those execution-time checks.

`run` re-admits the exact closed inputs, then reads only their bound `events.jsonl` and `PROCESS_SAMPLES.jsonl`. It hashes the precise binary bytes consumed while parsing once. Native event totals must reconcile with the worker result, and the terminal joined sample must match final state, event counts, source/ASR/speaker cursors, scheduler, event-log size and zero consumer queue. Bad/changed bytes, missing required fields, invalid closure, missing tail/drain or failed bounds stop the report. A failed report namespace is preserved; use a fresh namespace after a separately reviewed repair.

The shared `REPORT/PACED_QUIET_OWNER.json` must be absent at prepare/run and before/after each session's log reads. This check defers work during an existing paced/long lease; it is not a reservation against a coordinator starting concurrently. Root must schedule the report outside measurement intervals.

No private user gallery is opened. Fixed research roster/profile metadata arrives only through the admitted native chain.

## Outputs and field definitions

All report outputs go under `reports/S6C/20260910T123540Z/long_diagnostics/<fresh namespace>/`:

- `PLAN.json`: explicit closed admission bindings, exact helper/README/dependency bindings, retained metadata bindings and file/record limits. Status is prepared closed inputs, without a log scan.
- `metadata_snapshots/` and `execution_metadata/metadata_snapshots/`: exact metadata buffers consumed at preparation and execution respectively.
- `session_XX/RESULT.json`: direct native observations and original source bindings for each session.
- `NATIVE_TEXT_NAME_REVISION_OBSERVATIONS.jsonl.gz`: complete payloads of actual transcript, identity-decision and raw-ASR emissions; speaker decisions are an explicitly labeled projection including native lineage, labels, support and available-at fields. No vectors or correctness labels are added. The order is native log order. Existing returned fields retain their meaning.
- `NATIVE_ADMISSION_DEBT_CONTEXT_OBSERVATIONS.jsonl.gz`: role-level native admission/rejection, exact due-ledger rows, context stamp/age/empty/used state and selected hop. These are direct observations rather than reconstructed admission decisions.
- `ANALYSIS_RECEIPT.json`: results, source/metadata bindings and zero model/policy/PCM-read counts. No source binds its own bytes; the final receipt binds earlier outputs.

`facts.asr_dispatch.source_frames_from_dispatch_spans` is calculated from integer 16 kHz source endpoints. Native ordinary dispatches do not contain a samples field. Explicit final tail samples must additionally equal their source span. Conversion allows at most `1e-5` of one sample for binary floating-point representation, while adjacency and totals compare integer frames exactly. The final `research_asr_drain` is separately retained and its 0.66 seconds of synthetic padding are excluded from observed audio. Endpoint/advisor/reset flags are counted with their actual OR consistency; flags are not claims of word benefit or inferred causes.

`speech_context` reuses the held converter's pure function: short/mature roles are deduplicated by source end only after their shared context fields agree. Role policy is explicit. Active means the native first gate was not `no_speech_gate`; overlap can remain active. It is not truth speech or a per-track age. Empty and missing contexts keep distinct counts. The native due ledger acknowledges all due entries when a global window is admitted; it does not prove that each debtor's own voice was delivered.

Lifecycle operations come from actual decision `lineage`. Some valid early audio-gate rejections omit `lifecycle_counts`; their count observations remain missing. No zeros or prior counts are substituted. Reported track maxima therefore cover decision-time observations. Capacity rejection incidence and retained lineage remain available; continuous capacity-blocked seconds are not inferred from sparse events. The final scheduler/identity snapshot is preserved; no unavailable final tracker snapshot is invented.

`trajectory` has periodic, terminal, complete-tree and incomplete-tree denominators, the largest observed sample gap, first-sample offset, event-log growth and process membership changes. RSS is a sum upper bound; USS is private resident; Windows private commit is distinct. PSS/unique shared resident are unavailable in the original sampler. CPU/write values and deltas are sampled counters. Model load is a separate native result timer; process sampling begins after model startup and engine launch. Sampled maxima and first-to-last slopes do not establish continuous peaks or absence of a leak. Missing data are not interpolated. Scheduler `max_pending_events` is its own internal high-water count; sampled consumer `event_queue_backlog` is a different queue.

Native UTC emissions are relative to `source_started`. The preserved order is native emission order: source cursors may interleave or move backward across lanes, and records are not sorted by source time. Signed emission-minus-source-cursor offsets remain negative where observed, since source blocks are published before producer sleep. These are not GUI display, phonetic onset, physical microphone/DSP or CM5 latencies. Wall-clock reversals are counted and the first 100 retained without repair. Inclusive and nested compute fields stay separate; do not sum them as independent costs.

## Bounds

Each JSONL input is limited to 1 GiB, each line to 8 MiB and each stream to 1,000,000 records. The helper streams raw events but retains bounded projections and numeric summaries: at most 100,000 text/decision projections, 100,000 admission projections and 128 MiB of their serialized payloads. Process samples and numeric observation lists remain in memory up to the explicit stream limits; this is not a constant-memory claim. Bound violations are fatal, never truncated successes. Input metadata uses the held reader's 64 MiB per-file limit. Derived gzip payloads have zero header timestamp for reproducibility; hash/byte bindings cover the final compressed bytes.

## PowerShell commands

Use the existing pinned EDGE interpreter. Commands below only create a model-free check receipt until actual completed admissions are supplied. Replace example admission/plan paths and `ACTUAL_SHA256` with the exact reviewed bindings; do not use unfinished sources or fabricate acceptance.

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edge = Join-Path $repo '.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $edge -B "$sim\scripts\s6c_long_diagnostics_v1.py" checks --output "$sim\reports\S6C\20260910T123540Z\long_diagnostics\SOURCE_CHECKS_V1.json"

# Only after actual native closure and independent helper review:
& $edge -B "$sim\scripts\s6c_long_diagnostics_v1.py" prepare --namespace closed_continuous_v1 --admission 'C:\exact\ADMISSION.json' 'ACTUAL_SHA256'
& $edge -B "$sim\scripts\s6c_long_diagnostics_v1.py" run --plan "$sim\reports\S6C\20260910T123540Z\long_diagnostics\closed_continuous_v1\PLAN.json" 'ACTUAL_PLAN_SHA256'
```

Repeat `--admission PATH SHA256` to include multiple explicitly closed sessions. A namespace and each receipt must be fresh; no overwrite/cleanup action is provided.

## Anaconda Prompt / CMD commands

The explicit interpreter avoids relying on the currently activated Conda environment. No package installation is required.

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "EDGE=%REPO%\.edge-speech-env\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
"%EDGE%" -B "%SIM%\scripts\s6c_long_diagnostics_v1.py" checks --output "%SIM%\reports\S6C\20260910T123540Z\long_diagnostics\SOURCE_CHECKS_V1_CMD_REPRODUCTION.json"
"%EDGE%" -B "%SIM%\scripts\s6c_long_diagnostics_v1.py" prepare --namespace closed_continuous_cmd_v1 --admission "C:\exact\ADMISSION.json" "ACTUAL_SHA256"
"%EDGE%" -B "%SIM%\scripts\s6c_long_diagnostics_v1.py" run --plan "%SIM%\reports\S6C\20260910T123540Z\long_diagnostics\closed_continuous_cmd_v1\PLAN.json" "ACTUAL_PLAN_SHA256"
```

## Validation status

The `checks` action uses only tiny synthetic JSON/event/process fixtures plus exact local source pins. It checks native dispatch/tail/drain and signed clocks, role/context and lineage missingness, changed/malformed streaming bytes, quiet-lease refusal, finalization/drop/cursor guards and output paths. It does not execute or admit a real continuous session. The original long authority-chain validation belongs to the separately reviewed inventory V3. Actual result status is created only after complete source admission and log-byte/count reconciliation; until then this helper remains preparation code.
