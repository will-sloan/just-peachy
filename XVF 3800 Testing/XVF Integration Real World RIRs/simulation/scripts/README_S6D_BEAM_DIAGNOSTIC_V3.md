# Future diagnostic-only80GiB source migration

`s6d_beam_native_run_diagnostic_v3.py` copies the independently accepted diagnostic dual-journal V2 wrapper. Its only executable change is the protocol support pin874d→bdb989, the already accepted confirmation wrapperV3. Native engine classes, execution loop, input/source checks, both complete PCM spools, dispatch/drain, clocks, STOP and completion semantics are unchanged. Old C12/core, diagnosticV2 and all live sources remain unchanged.

`s6d_beam_queue_prepare_diagnostic_v3.py` copies the diagnosticV2 held-queue builder and binds the exact accepted runnerV5/57fb and documented80GiB exception079900. `payload_sources(manifest)` verifies source acceptance585c3db4, runnerfreezead06, wrapperfreezef1a4, all frozen source files and exact contract/forecast/priorV4 documents. No source acceptance grants execution approval.

The future diagnostic manifest must add these metadata fields: `payload_cap_exception` equals the exact079900 binding; `payload_source_acceptance` equals ROOT_SOURCE_ACCEPTANCE585c3db4; `support.runner` equals runnerV5/57fb; `support.protocol` equals wrapperV3/bdb989; `limits.max_new_payload_gib=80`. `runner_helper` binds this new diagnostic wrapper. Keep all literal528 tasks, frame/PCM/actual capture/profile/gallery/settings/window/source/output definitions unchanged. No production manifest is constructed by this source task.

Every proposed job guards the exact exception, contract, forecast and priorV4 source, plus root source acceptance, both accepted source freezes and the preparation helper/README. Queue `payload_policy` changes only the maximum to80GiB and adds `cap_exception`; the empty approval proposal adds the identical `payload_cap_exception`. The same three global census roots, C50/G75 floors, deadlines/reserve, watchdogs, dual-spool predicates and output semantics remain. V5's pure payload gate rejects missing job guards or mismatched/expired authority; runtime census/floors remain mandatory.

Inputs: future exact source-bound diagnostic manifest after actual96 MAIN/SCAN capture catalog qualification and this source's independent acceptance. Outputs: a fresh held queue, empty approval proposal and preparation receipt. The builder imports no engine or model. It neither creates root approval nor launches four workers. The existing132-per-worker membership,48 exact auto-control reuse conditions and exclusion of controlled native/C/core/Tk/HOST overlap remain those in `application/beam_diagnostic_readiness_v1/PLAN.json`.

`s6d_beam_diagnostic_payload_checks_v3.py` validates only the affected metadata: exact wrapper substitutions, unchanged dual-spool scientific/runtime AST and queue predicates, actual accepted payload graph, missing manifest fields, and pure extracted V5 guard against missing per-job authorities/wrong payload/changed roots. It imports no runner and creates no production inputs, queues or approvals. All tests use in-memory fixture metadata and write a small receipt under G. No audio/model/device/process queries occur; prior16+independent5 dual-spool checks are bound, not repeated.

PowerShell checks:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_beam_diagnostic_payload_checks_v3.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_payload_v3\checks_v1'
```

Anaconda Prompt / CMD checks:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_beam_diagnostic_payload_checks_v3.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_diagnostic_payload_v3\checks_v1"
```

Use fresh output suffixes. After actual input and source review, PowerShell held-metadata command is `& $py -B "$sim\scripts\s6d_beam_queue_prepare_diagnostic_v3.py" --manifest '<exact future manifest>' --manifest-sha256 '<SHA256>' --output '<fresh R runner directory>'`, where `$py` is the repository `.edge-speech-env\python.exe`. CMD uses `"%PY%" -B "%SIM%\scripts\s6d_beam_queue_prepare_diagnostic_v3.py"` with the same arguments. This produces an unapproved parent queue. Existing partition preparation may then preserve index-modulo4 membership in four held queues; root must separately approve exact job hashes, global slots and current resource state. Native execution remains supervisor-only with manifest/hash/job-ID and the required S6D ownership environment.

This is future offline80 only. It does not alter physical40GiB policy, add cases, reuse failed results, normalize inputs, extend time, or qualify future diagnostic outputs. Parallel timing remains descriptive and cannot become serial latency, causal availability, GUI rendering or scanout evidence.
