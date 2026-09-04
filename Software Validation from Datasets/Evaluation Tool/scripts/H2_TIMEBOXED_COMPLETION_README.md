# H2 Ten-Hour Completion Controller

## Deadline-bounded matched held-out panel

`h2_deadline_bounded_heldout.py` is the transparent fallback when measured
full-pipeline throughput makes the original 180-case by two-mode frozen
held-out campaign impossible before the user-authorized deadline. It does not
change model assets, thresholds, margins, enrollment, buffering, clustering,
or label policy. It takes a metric-blind prefix of the immutable held-out case
order, runs the memory-enhanced mode in a separate durable queue while the
original known-only mode continues, and requests a graceful stop at the same
complete-case boundary. The original full campaign and every completed shard
remain preserved.

Inputs are the v17 workspace, results and summary roots, frozen configuration,
case count, compute-stop time, and hard deadline. Outputs are the checksummed
panel plan, selected case manifest, durable memory-mode queue/result, progress
state, and bounded-result receipt under `timeboxed_completion` and
`deadline_bounded_heldout`. Concurrent accuracy timing is explicitly nonfinal;
accuracy and UX metrics remain valid for the selected matched panel.

From PowerShell or Anaconda Prompt, first write/verify the metric-blind plan:

```powershell
$Tool = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe'
$Workspace = Join-Path $Tool 'automated_runs\h2_complete_product_pipeline_v17'
$Results = Join-Path $Tool 'JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17'
$Summary = Join-Path $Tool 'JustPeachyResearchSummaries\h2_complete_product_pipeline_v17'
$Config = Join-Path $Tool 'configs\automated_evaluation\h2_product_program.v17.yaml'

& $Python -B (Join-Path $Tool 'scripts\h2_deadline_bounded_heldout.py') Plan `
  --tool-root $Tool --workspace $Workspace --results-root $Results `
  --summary-root $Summary --config $Config --case-count 24 `
  --compute-stop-utc '2026-09-01T14:07:00Z' `
  --hard-deadline-utc '2026-09-01T15:22:00Z'
```

Run the resumable second mode after the plan is sealed:

```powershell
& $Python -B (Join-Path $Tool 'scripts\h2_deadline_bounded_heldout.py') Run `
  --tool-root $Tool --workspace $Workspace --results-root $Results `
  --summary-root $Summary --config $Config --case-count 24 `
  --compute-stop-utc '2026-09-01T14:07:00Z' `
  --hard-deadline-utc '2026-09-01T15:22:00Z'
```

The same command with action `Status` reads progress without changing work.

`h2_deadline_known_boundary_watch.py` is the companion exact-boundary watcher.
It reads only progress counts and requests the normal graceful stop at N-1,
while the Nth case is active, so the original known-only run ends with the same
24 complete cases as the second mode. It never reads scores and never kills a
process. Its inputs are the same roots plus the frozen execution job ID, target
case count, and deadline; it writes a checksummed watcher receipt and result.

```powershell
& $Python -B (Join-Path $Tool 'scripts\h2_deadline_known_boundary_watch.py') `
  --tool-root $Tool --workspace $Workspace --results-root $Results `
  --summary-root $Summary --config $Config `
  --execution-job-id 'h2eval_803ba2ccf2530618fbd5fced' `
  --target-completed-cases 24 --deadline-utc '2026-09-01T14:07:00Z'
```

`h2_deadline_final_consolidation.py` waits for both exact matched result trees,
validates their checksums and completed-case identities, calculates the final
critical metric tables and the 2,000-repetition speaker-cluster bootstrap,
documents metric definitions and limitations, ranks the two modes with the
predeclared safety-first ordering, and creates the compact upload ZIP. Inputs
are the tool/workspace/result/summary roots, hard deadline, and optional main
manager PID. Outputs include `DEADLINE_PANEL_ALL_METRICS.csv`,
`DEADLINE_PANEL_CRITICAL_METRICS.csv`, bootstrap and failure tables,
`FINAL_PIPELINE_REPORT.md`, `REPRODUCIBILITY_MANIFEST.json`, the result
inventory, and `H2_TIMEBOXED_FINAL_RESULTS.zip`. It includes no raw dataset,
model weight, credential, or cache.

The wait loop performs only cheap path checks until both result trees have been
published; it does not repeatedly hash a partial tree while inference is still
running. Deep schema/checksum validation remains mandatory once both candidates
exist. `RESULT_FILE_INVENTORY.csv` is deliberately excluded from its own
pre-ZIP hash listing and is then included as a normal ZIP member, avoiding an
impossible stale self-hash.

```powershell
& $Python -B (Join-Path $Tool 'scripts\h2_deadline_final_consolidation.py') WaitAndBuild `
  --tool-root $Tool --workspace $Workspace --results-root $Results `
  --summary-root $Summary --hard-deadline-utc '2026-09-01T15:22:00Z' `
  --manager-pid 40120
```

Use action `Status` for a read-only readiness check or `Build` to fail fast if
either exact panel result is not ready.

`h2_deadline_sequential_retry.py` handles the recorded Windows shared-cache
write collision discovered during the permitted two-job accuracy launch. It
waits for the memory panel to close its workers by reading the authoritative
durable SQLite queue state, verifies the known-only failure state, records a
checksummed implementation-bug receipt, and invokes the already-activated,
checksum-bound selector-correction continuation launcher with concurrency one.
It deliberately does not reuse the pre-held-out timeboxed freeze override,
which is ineligible after the frozen evaluation boundary opens. Completed case
shards are reused; the unsealed failed case is recomputed. No scientific parameter is
changed, and concurrent timing is invalidated. The receipt records the observed
stale derived progress state and terminal durable queue state so this
orchestration-only correction remains auditable. Inputs are the standard roots,
frozen config, and compute-stop time; outputs are retry logs and receipt/result
JSON under `timeboxed_completion`.

```powershell
& $Python -B (Join-Path $Tool 'scripts\h2_deadline_sequential_retry.py') `
  --tool-root $Tool --workspace $Workspace --results-root $Results `
  --summary-root $Summary --config $Config `
  --compute-stop-utc '2026-09-01T14:07:00Z'
```

If Windows instead denies an atomic publication inside the isolated memory
panel queue, first verify the durable job is failed and lease-free. Then rerun
the identical checksum-bound `h2_deadline_bounded_heldout.py Run` command with
the same roots, case count, and cutoff times. The queue claims a new attempt,
preserves sealed shards, and recomputes only the failed/unsealed case and the
remaining cases. Record the recovery in
`timeboxed_completion\deadline_memory_retry_receipt.json`; do not change the
plan, cases, frozen policy, or runtime configuration. Interrupted-attempt timing
is nonfinal.

### Deadline-only direct known retry contingency

`h2_deadline_direct_known_retry.py` is an orchestration-only fallback when the
normal post-freeze `Resume` remains in whole-program identity validation long
enough to threaten the compute cutoff. Never run it concurrently with another
program controller. It verifies the frozen policy and held-out manifest hashes,
the exact execution-job identity, immutable ordered 24-case prefix, and durable
queue specification before calling the existing `run_runtime_job`. It preserves
sealed shards, uses concurrency one, installs the existing Windows atomic
publication retry, enforces the 35 GiB C: reserve, and stops only at the 24-case
boundary or compute cutoff. It does not inspect metrics or change tuning.
The contingency uses the Python standard-library disk-usage query because the
host's Anaconda `psutil` extension raises a Windows ABI `SystemError`; the
reserve threshold and stop behavior are unchanged.

Preflight from PowerShell or Anaconda Prompt:

```powershell
& $Python -B (Join-Path $Tool 'scripts\h2_deadline_direct_known_retry.py') `
  --tool-root $Tool --workspace $Workspace --results-root $Results `
  --summary-root $Summary --config $Config --target-cases 24 `
  --compute-stop-utc '2026-09-01T14:07:00Z' --preflight-only
```

Remove `--preflight-only` only after proving that the normal controller has
exited, its campaign lock is released, and the durable known-only queue has no
running lease.

On Windows, do **not** poll an active
`runtime_cases\<case_id>\status.json` directly. A reader can briefly deny the
runtime's atomic replacement of that file. Monitor the durable SQLite queue,
campaign progress, sealed `case_shards_v1` entries, process activity, and
finalized result files instead. Reading a status file is safe only after that
case or attempt is terminal.

## Purpose

`h2_timeboxed_completion.py` applies the user-authorized hard deadline without deleting or rewriting completed evidence. It waits for the active development evaluation to finish at a controller boundary, records a checksum-bound pre-held-out scope amendment, evaluates the two retained H2 product modes on held-out data, uses remaining time for critical application/reliability/ONNX/ARM64 checks, and creates a compact analysis ZIP.

The controller does not tune models or policies. Long-session expansions, the third product mode's held-out repeat, and repeated native diagnostics are explicitly recorded as deferred.

The original freeze gate expected three long serial-resource rows before held-out. After the first case measured an RTF that made this incompatible with the hard deadline, scope-amendment revision 3 moved those engineering measurements after the scientific gate. `h2_timeboxed_freeze_bootstrap.py` is checksum-bound by that revision and may run only while held-out remains unopened. It still verifies all three matched development modes and their exact selected tuning; it does not change a model, threshold, policy, selected mode, or evaluation case.

The original manifest bootstrap also expects every extended held-out expansion. The checksum-bound `critical_analysis_plan.json`, written before held-out opens, instead applies the same 2,000-repetition, seed-3800 speaker-cluster bootstrap to the two retained product modes. This produces `BOOTSTRAP_INTERVALS.csv` during final reporting without inspecting held-out data for tuning or selection.

`h2_deadline_packaging_guard.py` is a non-scientific fail-safe. It is registered before held-out opens, does not select or retune anything, and normally remains idle. Ten minutes after the compute cutoff it may terminate only the active campaign child pass so the main manager can package. If no fresh checksum-valid ZIP exists 30 minutes before the hard deadline, it terminates the stalled manager tree and runs the exact reporter hash recorded in `critical_analysis_plan.json`.

Example direct launch from PowerShell or Anaconda Prompt (normally the campaign launches this hidden):

```powershell
python scripts\h2_deadline_packaging_guard.py --tool-root "." --workspace "automated_runs\h2_complete_product_pipeline_v17" --results-root "JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17" --summary-root "JustPeachyResearchSummaries\h2_complete_product_pipeline_v17" --manager-pid <PID> --compute-stop-utc "2026-09-01T14:07:00Z" --deadline-utc "2026-09-01T15:22:00Z"
```

Inputs are the campaign paths, manager PID, and UTC cutoff times. Outputs are an immutable startup receipt, an audit JSONL log, and—only on emergency fallback—the same compact results ZIP produced by the bound reporter.

## Inputs

- Existing H2 v17 workspace and `program_state.json`
- Frozen `job_manifest.json` and protocol manifest
- Existing result/cache root on C:
- Frozen v17 YAML configuration
- An absolute UTC deadline and packaging reserve

## Outputs

- `workspace\timeboxed_completion\scope_amendment.json`
- `workspace\logs\timeboxed_completion.jsonl`
- `summary\FINAL_TIMEBOXED_REPORT.md`
- `summary\METRIC_GUIDE.md`
- `summary\TIMEBOXED_CRITICAL_METRICS.csv`
- `summary\TIMEBOXED_ALL_METRICS.csv`
- `summary\TIMEBOXED_JOB_INVENTORY.csv`
- `summary\REPRODUCIBILITY_MANIFEST.json`
- `summary\H2_TIMEBOXED_FINAL_RESULTS.zip`
- `summary\UPLOAD_THIS_FILE_TO_CHATGPT.txt`

## PowerShell / command-line launch

Open PowerShell in the Evaluation Tool directory:

```powershell
cd 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& '..\..\.venv\Scripts\python.exe' -B '.\scripts\h2_timeboxed_completion.py' `
  --tool-root (Get-Location).Path `
  --workspace '.\automated_runs\h2_complete_product_pipeline_v17' `
  --results-root '.\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17' `
  --summary-root '.\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17' `
  --config '.\configs\automated_evaluation\h2_product_program.v17.yaml' `
  --deadline-utc '2026-09-01T15:22:00Z' `
  --packaging-reserve-minutes 75
```

## Anaconda Prompt

No activation is required when the repository interpreter above exists. From Anaconda Prompt, run the same command on one line, or activate the project environment if that is how the repository was originally configured and replace the interpreter with `python`.

## Monitor without changing the run

```powershell
Get-Content '.\automated_runs\h2_complete_product_pipeline_v17\logs\timeboxed_completion.jsonl' -Tail 30 -Wait
```

Current campaign state:

```powershell
Get-Content '.\automated_runs\h2_complete_product_pipeline_v17\program_state.json' -Raw | ConvertFrom-Json | Select-Object status,detail,current_job_id,updated_at_utc
```

## Verify the export

```powershell
$pointer = Get-Content '.\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\UPLOAD_THIS_FILE_TO_CHATGPT.txt'
Get-FileHash '.\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\H2_TIMEBOXED_FINAL_RESULTS.zip' -Algorithm SHA256
```

The computed hash must equal the SHA-256 in `UPLOAD_THIS_FILE_TO_CHATGPT.txt`.

## Developer tests

```powershell
& '..\..\.venv\Scripts\python.exe' -B -m pytest '.\tests\test_h2_timeboxed_completion.py' -q
```

`watch_h2_timeboxed_second_pass.ps1` is a handoff helper for the already-running first controller instance. It waits for that exact PID and then relaunches the idempotent controller so post-freeze engineering jobs can use remaining time even if the original built-in finalizer rejects the deliberately superseded long jobs. It uses the same inputs and absolute deadline and never duplicates an active pass.

## Safety and restart behavior

- A stop request is graceful until the absolute deadline.
- At the absolute deadline, only the exact child process started by this controller is terminated.
- Completed job rows and result directories are never removed.
- The scope amendment is idempotent and checksum-validated on restart.
- If interrupted, run the same command with the same deadline. The controller reuses completed jobs and existing receipts.
