# S6D code-only frozen-queue supervisor

Purpose: run only an explicitly approved immutable local job queue, observe progress and resources, validate declared artifacts and preserve resumable checkpoints. This is a local Python supervisor, not a ChatGPT automation or an unattended model interpreter. The existing continuation capability did not qualify; this implementation writes a manual RESUME_REQUEST.json containing the exact owner task/session, queue/approval hashes, checkpoint and explicit resume argv. It never starts a new App Server, account session, agent framework, reminder, model review or arbitrary log-derived command. No production queue has yet been supplied or executed by this framework.

Dependencies: existing native Python 3.11 and psutil. No install or conda activation is required. The script uses shell=False and CREATE_NO_WINDOW on Windows. Every job must name an absolute allowlisted executable, absolute hash-bound entry script and approved working directory. Inline -c/-Command/eval and shell interpreters are rejected. A separate checksummed approval document binds the queue and each complete job spec; it must cite actual root/user authorization. Data or model logs cannot approve themselves.

Queue input schema s6d_approved_job_queue_v1:

- run_id, owner_thread_id, owner_session_id and runner_sha256 are required. A nonfixture queue also requires campaign with started_utc=2026-09-13T19:53:57+00:00, deadline_utc no later than2026-09-16T19:53:57+00:00 and closeout_reserve_s>=2700. Work ends at deadline minus reserve (at latest2026-09-16T19:08:57+00:00). A next job must fit its declared timeout plus stop grace before that work deadline; every health cycle also enforces it. A new runner/resume cannot reset campaign time.
- jobs is an ordered list; each job has job_id (letters/digits/underscore/hyphen), kind=offline or hardware, workload=sensitive/normal/cached, literal argv, cwd and source_bindings entries {path,sha256,bytes}.
- Each job declares unique fresh heartbeat_path and completion_path, stop_request_path, timeout_s, stall_after_s, heartbeat_stale_s, stop_grace_s, allow_owned_termination and expected_artifacts. Hardware also declares restoration_path and cannot permit termination.
- expected_artifacts entries are either {path,format:json,min_bytes,expected_fields:{dotted.field:expectedValue}} or {path,format:exact_file,min_bytes,sha256}. Every job needs explicit predicates; exit0 alone never means scientific PASS.
- payload_policy has new_payload_roots covering all new payload for the run and max_new_payload_bytes <=42949672960 (40 GiB). Roots must fall under approved outputs. Counts include files already present in those new-run roots, are deduplicated by resolved path and sampled each60s. This is not a fast hardware watchdog; hardware transport retains its independent guard.
- disk_policy entries {path,minimum_free_bytes} must retain the campaign floors C:>=53687091200 and G:>=80530636800 bytes; admission rejects absent/weaker production floors. Disk is checked before spawn and on each15s health cycle. Empty fixture policy is allowed only when fixture_only is explicitly true. All durations, sizes and budget policies reject NaN/infinity and booleans.
- optional environment overrides are part of the approved job digest; HOME/CODEX_HOME/USERPROFILE and S6D_* identity overrides are rejected case-insensitively. Optional fixture_only permits accelerated fixture cycles through the Python API, never through production CLI.

Approval schema s6d_queue_approval_v1 requires run_id, queue_sha256, authorization_ref, approved_job_sha256 (stable JSON digests of complete job specs), executable_bindings, allowed_working_directories and allowed_output_roots. Hashes are passed explicitly on the CLI so changing a queue/approval requires deliberate approval/rebinding. The root prepares this file; the supervisor does not fabricate user authorization.

Periodic source_bindings are limited to small executable code/configuration files (<=16MiB each,<=64MiB total per job). Large model/audio assets must be hash-bound once by the frozen child manifest/initialization and referenced by their receipts; never put multi-GiB model assets in15second source rehash loops.

Child protocol: environment supplies S6D_RUN_ID, S6D_JOB_ID, S6D_CHILD_RUN_ID, S6D_HEARTBEAT_PATH, S6D_COMPLETION_PATH and S6D_STOP_REQUEST_PATH, plus S6D_RESTORATION_PATH for hardware. The child heartbeat JSON must include run_id,job_id,child_run_id,pid,creation_time (psutil seconds), status and monotonically increasing progress_count. queue_age_s is optional; absent means null. Heartbeat interruption can explicitly be AUTH_REQUIRED or QUOTA_EXHAUSTED, which blocks without retry. Child completion must match run/job/child IDs with status=COMPLETE; the declared artifacts are validated separately. A hardware restoration receipt must match those IDs and contain status=RESTORED and verified=true. Existing production jobs need an explicitly frozen compatible wrapper or hooks before admission; this framework does not manufacture their progress/receipts.

Health is sampled every15s, local supervisor heartbeat every30s. At10/15/30min interpretation opportunities (sensitive/normal/cached), a small receipt records whether state changed; no automatic model turn is requested. The <=2048-byte STATUS_DELTA provides stage, done/total, elapsed, unknown ETA as null, resource maxima and exact local pointers. Full health logs and child stdout stay local. psutil captures process-tree RSS/USS/PSS where available, process count and system available RAM. Missing PSS/queue age/model usage stay null. Keep the approved payload roots bounded; logs are not silently deleted to satisfy a limit.

Only WAIT, ADVANCE_CHECKPOINT, REPORT_BLOCKED, REVIEW_FAILURE and FINISH are controller actions. FINISH closes the supplied queue only. Semantic artifact validation and exact completed hashes prevent an exit0 or later-mutated artifact from becoming success. The owner lock precedes launch. Launch intent is durable before spawn; an interrupted launch intent blocks reconciliation instead of duplicating a job. PID+creation and child-run IDs prevent PID-reuse confusion. A live child with stale heartbeat remains distinct from a declared progress stall. Bounded partial-JSON retries tolerate incomplete atomic/streamed writes without an unbounded loop.

On a declared failure the supervisor writes STOP_REQUEST and allows the declared grace. Only explicitly authorized offline children may then be terminated, and only after exact PID+creation verification. No process-name kill, unrelated descendants or H2 process is targeted. Hardware is never terminated: it must exit with verified restoration, or a blocking lock and HARDWARE_RESTORATION_PENDING flag remain for explicit recovery. A new runner cannot silently take over that lock. The independent hardware watchdog must remain effective while any supervisor or model is idle. Supervisor exceptions also signal the active child through this path.

Optional --keep-awake acquires only an owned Windows execution-state request (no display wake), restores it on exit and records success/failure. Default is no keep-awake change. A failed owned restoration reports blocked. Fixture tests use a simulated API only and never alter the host's power state.

Run validation first in PowerShell after the coordinator has supplied an actual approved queue:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$queue = "$sim\reports\S6D\20260913T195357Z\runner\APPROVED_QUEUE.json"
$approval = "$sim\reports\S6D\20260913T195357Z\runner\QUEUE_APPROVAL.json"
$queueHash = (Get-FileHash -LiteralPath $queue -Algorithm SHA256).Hash.ToLowerInvariant()
$approvalHash = (Get-FileHash -LiteralPath $approval -Algorithm SHA256).Hash.ToLowerInvariant()
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6d_runner_v1.py" --queue "$queue" --approval "$approval" --queue-sha256 "$queueHash" --approval-sha256 "$approvalHash" --state-dir "$sim\reports\S6D\20260913T195357Z\runner\production_state" --validate-only
```

After actual approval and successful validation, repeat the same command without --validate-only to execute. To resume, use the exact same queue/approval/hash/state parameters or the structured resume_argv from RESUME_REQUEST.json. Already completed jobs are revalidated and skipped. A blocked/failed job is not automatically retried into a new output; declare and approve a distinct attempt when root has resolved its cause.

Anaconda Prompt or Command Prompt (replace the two placeholders with the actual approved hashes; do not paste placeholders as evidence):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_runner_v1.py" --queue "%SIM%\reports\S6D\20260913T195357Z\runner\APPROVED_QUEUE.json" --approval "%SIM%\reports\S6D\20260913T195357Z\runner\QUEUE_APPROVAL.json" --queue-sha256 ACTUAL_APPROVED_QUEUE_SHA256 --approval-sha256 ACTUAL_APPROVAL_SHA256 --state-dir "%SIM%\reports\S6D\20260913T195357Z\runner\production_state" --validate-only
```

These production paths are documented interfaces and are not claims that those files exist. For the immediately executable model-free verification commands, see s6d_runner_fixtures_README.md. Outputs are CHECKPOINT, STATUS_DELTA, HEARTBEAT, local health/check-in/child logs, launch/closure receipts, manual resume request and any explicit block flag under the supplied state directory. Exit2 signals a blocked/failed queue; exit0 only follows validation-only or a completely validated approved queue.
