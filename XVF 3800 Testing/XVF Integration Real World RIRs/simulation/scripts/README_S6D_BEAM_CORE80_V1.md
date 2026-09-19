# Future serial core96 V5/80 source proposal

This additive source pair prepares future core96 execution under the exact already accepted V5 runner, V3 native protocol and justified80GiB exception. It does not migrate C12 or modify old C/core sources, application classes, queues, manifests or approvals. No production manifests or queues were constructed for this source proposal.

`s6d_beam_native_run_core80_v1.py` copies accepted original N6f (`6f716290`). Only its documentation, protocol pin (`874d` to `bdb989`) and a core-only admission predicate change. The new source accepts exactly96 unique MAIN jobs: both original modes (`same_pass_auto_control`, `mono_asr_beam_identity`) for each of48 cases, the fixed auto-ASR input, one serial model stack, at most two focus states, affinity12–15 and one thread per backend. It requires the new manifest's explicit integer80GiB limit. C collection and per-stream diagnostics reject before native dependency/process work. All original waveform, source/route/PCM, calibration, selected-person, model loop, clocks, queues, multistream journals, STOP, consumer and completion logic remains unchanged. This does not include the distinct diagnostic dual-spool repair.

`s6d_beam_queue_prepare_core80_v1.py` is a separate copy of the original held queue builder. Its new file-only authority check requires root source acceptance585c3db4, runner freezead06ac96, wrapper freezef1a4cf45, runner57fb87aa, wrapperbdb989 and exception079900e5. Every job guards the exact exception, contract, whole-study forecast and prior V4 runner, plus source acceptance and both source freezes. The new builder/README are guarded too. It changes only the queue's runner binding and payload ceiling plus exception; all shared census roots, C50/G75 floors, campaign deadline/45-minute reserve, literal artifacts, timeouts and STOP policies remain inherited. Approval proposals retain an empty approved-job list and bind the same exception. Actual V5 validation repeats its complete exception/floor/deadline guard at admission/run time.

The future manifest must retain the original frozen `beam_execution_predecl_v3/PROSPECTIVE_PLAN.json` binding (`01d2387b`), its ordered96 core tasks, original app/asset graph, profile, A15 gallery, settings and all execution limits. Its only limit addition is `max_new_payload_gib:80`; top-level `runner_helper` must bind the new core wrapper, `support.protocol` the exact V3 wrapper, `support.runner` the exact V5 runner, `payload_cap_exception` exception079900 and `payload_source_acceptance` root acceptance585c. Other native/source metadata and original calibrated beam settings stay unchanged. Materializing that manifest is a separate root-reviewed step using actual accepted captures and C-only calibration; this proposal does not fabricate those inputs.

The future held queue is one serial96 queue with existing960s supervisor timeout,300s stall threshold,45s stale heartbeat and75s STOP grace. It does not authorize overlapping neural sessions or an extra scientific grid. At actual admission root must verify enough remaining campaign time, resources and correct accepted C calibration/source support; after892 or late in the campaign cannot imply a deadline extension. Physical480-pass/21600-second limits, retention and all deferred BXR requirements remain unchanged. An80GiB source budget alone grants no scientific PASS.

## Inputs and outputs

The queue builder takes `--manifest EXACT_FUTURE_MANIFEST.json --manifest-sha256 SHA256 --output FRESH_R_RUNNER_DIRECTORY`. It produces only `QUEUE.json`, an unapproved `APPROVAL_PROPOSAL.json`, and `QUEUE_RECEIPT.json`. Future job/native/protocol outputs use the exact supplied manifest paths and must be fresh. It does not create root admission, start a supervisor, run a model or access a device.

The runner CLI is for an explicitly approved owner supervisor only: `--manifest`, `--manifest-sha256`, and `--job-id`, together with the inherited exact `S6D_*` ownership, heartbeat, completion and STOP environment. It writes the unchanged native RESULT, full multistream audit and protocol completion after actual full-source/closure validation. Do not start it outside that admission path.

PowerShell held metadata preparation, only after the future manifest is separately reviewed:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_beam_queue_prepare_core80_v1.py" --manifest 'EXACT_FUTURE_CORE_MANIFEST' --manifest-sha256 'MANIFEST_SHA256' --output "$sim\reports\S6D\20260913T195357Z\runner\FRESH_CORE80_PROPOSAL"
```

Anaconda Prompt / Windows CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_beam_queue_prepare_core80_v1.py" --manifest "EXACT_FUTURE_CORE_MANIFEST" --manifest-sha256 "MANIFEST_SHA256" --output "%SIM%\reports\S6D\20260913T195357Z\runner\FRESH_CORE80_PROPOSAL"
```

## Focused model-free source checks

`s6d_beam_core80_checks_v1.py` reads exact frozen source/authority/declaration metadata and constructs only synthetic in-memory manifest/queue-policy objects. It tests core-only scope, the exact source/budget authority, unchanged root/limit/order guards, all four exception bindings and unchanged scientific AST. No actual source audio, outputs, processes, models or queues are read or executed. The only outputs are a fresh G `RECEIPT.json` and the caller's redirected log. Inputs are `--source-root` containing this pair, README, and unchanged old prepare/import files, plus a fresh `--output` under G review_fixtures.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_beam_core80_checks_v1.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_core80_v1\checks_v1'
```

Anaconda Prompt / Windows CMD:

```bat
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_beam_core80_checks_v1.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_core80_v1\checks_v1"
```

Use a new output suffix if occupied. PASS is source/fixture readiness only; actual captures, C thresholds, output paths, budget availability and production approval remain unverified.
