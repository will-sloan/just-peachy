# S7 bounded serial supervisor

Purpose: run only a root-authorized, immutable literal queue and validate each job's exact declared completion/artifact predicates. This is an adaptation of the accepted S6D source_epoch_payload_v5 supervisor (SHA25657fb87aaba12495f724adbcc78a2609f82a897dd5d3877e6a2cabd54a68a7978), not another agent framework. Original S6D code, queues and outcomes remain untouched. It installs no automation and launches no model reasoning. Preparation and fixtures are not production qualification.

Files: s7_runner_v1.py contains the runner and prepare_queue(spec, output) API; test_s7_runner_v1.py reuses the original S6D fixture builder and tiny child protocol. This README covers both. Existing EDGE Python3.11/psutil is sufficient; no install/Conda activation or hardware is needed.

## Fixed scope and preserved behavior

- S7 run20260917T141700Z starts2026-09-17T14:17:00Z, ends2026-09-20T14:17:00Z. Reserve is at least3600s. Latest work cutoff is2026-09-20T13:17:00Z; a larger reserve advances it. Resume does not reset these clocks. Each next job's timeout plus stop grace must fit, and active jobs enforce the cutoff every health cycle.
- New payload ceiling is40GiB; the prior S6D80GiB exception is rejected. Production accounting must include both this complete S7 report root and G:\Just_Peachy_S7\20260917T141700Z. Output roots must stay within these. Root must create the declared payload directory before runtime; unresolved census roots block admission. C: free space must remain>=50GiB and G:>=75GiB.
- Only offline jobs are admitted. Historical hardware/restoration machinery is preserved but unreachable through S7 admission. No playback, capture or CM5 execution is authorized by this runner. A code allowlist is not a substitute for root's scientific authorization of the supplied job.
- Original PID/creation ownership, owner nonce, launch intent, child identity, source hash, exact completion predicates, completed-artifact revalidation, stop/grace, bounded owned offline termination and manual resume behavior are unchanged. No shell/eval/log-derived command is accepted. Unknown/stale heartbeat is distinct from dead child or declared progress stall.
- Async directory-batched payload census and bounded atomic-write retry remain unchanged. Census is not a full-drive scan or scientific event monitor. Failed/partial attempts remain. No evidence is deleted to meet budget. Storage and owner observations retain their inherited scope/limitations.
- Health15s and heartbeat30s remain.10/15/30-minute interpretation opportunities are code receipts only, with no automatic model calls. Root's user-facing hourly reporting remains external. Timed workers must supply their own lightweight per-block/one-second observations; this supervisor's15s health samples are not peak or GUI-latency proof. Keep timed native jobs serial and otherwise quiet.
- Optional inherited --keep-awake is off by default; use only if separately authorized. Fixtures never change power state.

The only inherited executable-body edits are S7 admission: queue/approval schema, exact campaign dates/reserve, offline-only jobs, whole-S7 roots and strict40GiB. Two report strings now say S7. New preparation functions bind metadata only. Fixtures compare every other inherited function/class AST, including launch/stop/owner/census/resume. Existing S6D_* child protocol is intentionally unchanged.

## Root supplies inputs

Create a literal JSON spec with run_id="20260917T141700Z", owner_thread_id, owner_session_id, authorization_ref identifying actual root authorization, optional closeout_reserve_s>=3600, and jobs (nonempty ordered list). The builder records that supplied authorization; it does not infer user consent or select experiments.

Each job needs:

- job_id: unique letters/digits/underscore/hyphen, kind="offline", workload="sensitive"/"normal"/"cached".
- argv: literal array beginning with absolute allowlisted Python executable and absolute entry-script path, then that script's arguments. Do not insert -B between those first two elements; PYTHONDONTWRITEBYTECODE may be a declared environment override. No -c/-Command/eval, shell or arbitrary command text.
- cwd: existing absolute working directory; source_bindings: {path,bytes,sha256} for the entry script and all relevant small frozen code/config dependencies. Each<=16MiB and total<=64MiB. Large models/audio are bound once by the child manifest, never rehashed every health cycle.
- Unique fresh heartbeat_path, completion_path, stop_request_path; timeout_s, stall_after_s, heartbeat_stale_s, stop_grace_s positive finite numbers; allow_owned_termination explicitly set according to root authorization. Optional environment overrides cannot replace HOME/CODEX_HOME/USERPROFILE or S6D_* identity variables.
- expected_artifacts: nonempty predicates. JSON entries use path,format="json",min_bytes,expected_fields={"dotted.field":expectedValue}; exact files use path,format="exact_file",min_bytes,sha256. Exit0 without these proofs cannot succeed.

Queue schema is s7_approved_job_queue_v1; approval schema is s7_queue_approval_v1. Preparation freezes runner/executable/source/job hashes and outputs QUEUE.json, APPROVAL.json, PREPARATION.json under a fresh child of this runner directory. No jobs start. There is no blanket authorization template populated with invented jobs.

Child environment: S6D_RUN_ID, S6D_JOB_ID, S6D_CHILD_RUN_ID, S6D_HEARTBEAT_PATH, S6D_COMPLETION_PATH and S6D_STOP_REQUEST_PATH. Heartbeat includes run_id/job_id/child_run_id/pid/creation_time,status,monotone progress_count; queue_age_s may be null. Completion matches run/job/child identity and status="COMPLETE", followed by all artifact predicates. AUTH_REQUIRED/QUOTA_EXHAUSTED block without automatic retries. Child must observe STOP_REQUEST and close its owned work. Root's native wrapper must explicitly implement this protocol; the runner cannot manufacture completion.

## PowerShell

```powershell
$runnerRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\runner'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
# Immediately runnable model-free fixtures; use a new output name on repeats.
& $edgePython -B "$runnerRoot\test_s7_runner_v1.py" --output "$runnerRoot\source_checks_v1"
# Root supplies this actual JSON first; the example path is not a claimed file.
& $edgePython -B "$runnerRoot\s7_runner_v1.py" prepare --spec "$runnerRoot\ROOT_AUTHORIZED_JOBS.json" --output "$runnerRoot\queue_v1"
$queue = "$runnerRoot\queue_v1\QUEUE.json"
$approval = "$runnerRoot\queue_v1\APPROVAL.json"
$queueHash = (Get-FileHash -LiteralPath $queue -Algorithm SHA256).Hash.ToLowerInvariant()
$approvalHash = (Get-FileHash -LiteralPath $approval -Algorithm SHA256).Hash.ToLowerInvariant()
& $edgePython -B "$runnerRoot\s7_runner_v1.py" --queue $queue --approval $approval --queue-sha256 $queueHash --approval-sha256 $approvalHash --state-dir "$runnerRoot\queue_v1\state" --validate-only
# Root alone launches: repeat the last command without --validate-only.
```

## Anaconda Prompt / CMD

Use existing EDGE directly; no activation. Replace ACTUAL_* hashes with the exact prepared values.

```bat
set "RUNNER_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\runner"
set "EDGE_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%EDGE_PYTHON%" -B "%RUNNER_ROOT%\test_s7_runner_v1.py" --output "%RUNNER_ROOT%\source_checks_v1"
"%EDGE_PYTHON%" -B "%RUNNER_ROOT%\s7_runner_v1.py" prepare --spec "%RUNNER_ROOT%\ROOT_AUTHORIZED_JOBS.json" --output "%RUNNER_ROOT%\queue_v1"
"%EDGE_PYTHON%" -B "%RUNNER_ROOT%\s7_runner_v1.py" --queue "%RUNNER_ROOT%\queue_v1\QUEUE.json" --approval "%RUNNER_ROOT%\queue_v1\APPROVAL.json" --queue-sha256 ACTUAL_QUEUE_SHA256 --approval-sha256 ACTUAL_APPROVAL_SHA256 --state-dir "%RUNNER_ROOT%\queue_v1\state" --validate-only
```

Validation-only creates the state directory and checks exact inputs; it starts no job/census/power request. Root removes --validate-only only for authorized execution. Resume uses the same exact queue/approval/state arguments, or structured resume_argv from RESUME_REQUEST.json, never --last. Completed artifacts are revalidated and skipped; failed/blocked output is preserved. Root must resolve the cause and bind a distinct new attempt for an authorized retry, rather than silently overwriting output.

## Outputs and verification

Runtime outputs: CHECKPOINT.json, STATUS_DELTA.json (bounded2KiB), HEARTBEAT.json, HEALTH.jsonl, check-in/child logs, exact launch/closure metadata, owner lock/immutable closed-lock receipts, and manual RESUME_REQUEST.json. FINISH closes only the approved queue, not S7/GateA/scientific acceptance. Exit2 reports blocked/failed; exit0 means validation-only or exact completed queue. All new persistent code is listed above and covered here.

Fixtures create two tiny Python metadata-only children in a private fixture namespace, reusing existing S6D fixture machinery. They check successful receipt/resume without relaunch, changed completion rejection, failed child, stale-vs-stall semantics, source/owner guards, S7 date/reserve/disk/cap/root admissions, a mocked production cutoff before Popen, and metadata-only builder. No model/audio/hardware, production census, unrelated termination or automation occurs. SOURCE_CHECKS.json binds source/README/base/fixtures and each result. Fixture_only is a test API convention, never a qualifying S7 production queue.
