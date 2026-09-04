# H2 storage guardian

## Purpose

`maintain_h2_storage.py` prevents a long H2 product-pipeline campaign from
retaining large restart intermediates after their scientific results have been
sealed. It is deliberately separate from the frozen inference/controller code,
so enabling it does not change the campaign's result-affecting runtime identity.

The guardian keeps all data on C:. It never removes raw/source audio, model
weights, enrollment profiles, campaign databases, or scientific result trees.
It considers only a job's `case_shards_v1` directory, and only when the
transactional queue says every case is complete. Shared inference caches remain
available through the last planned neural consumer. After that point they are
marked for an ownership audit: compact content-address maps and hashes are
retained, and only entries proven unused by every active campaign may be
removed. Blind deletion of the global cache is forbidden.

There is one additional non-destructive safeguard for the unusually large
30–60 minute long-session jobs. When the conservative forecast is
`EARLY_RECLAIM` or `CRITICAL_RECLAIM`, the guardian marks the exact active
long-session `case_shards_v1` directory for inherited, lossless NTFS
compression. Future restart files then consume fewer allocated bytes while
retaining identical logical content. This is never enabled for matched serial
resource measurements, because filesystem compression could bias CPU or I/O.

Before removal it verifies:

1. the queue job is complete and has every expected case;
2. every shard has its exact internal checksum, job identity, reuse identity,
   case identity, and ordinal;
3. the sealed result has the exact queue-recorded `checksums.json` SHA-256;
4. the whole result tree passes the repository's immutable reuse validator;
5. its portable case references exactly match the queue case list.

It then writes a durable pending receipt, removes only the exact validated
restart-intermediate directory, and writes a signed final receipt. The receipt
maps every case ID, case identity, former shard checksum, portable-reference
checksum, frozen manifests, runtime identity, config, queue database, and
retained result. This preserves auditability and tells a future operator exactly
what to rerun without storing duplicate payloads that are not used again.

## Inputs and outputs

Inputs:

- `--workspace`: the existing H2 campaign workspace on C:;
- `--results-root`: the existing sealed H2 results root on C:;
- the campaign SQLite queues, frozen manifests, completed shard trees, and
  sealed results already below those locations.

Outputs below `<workspace>\storage_maintenance`:

- `receipts\*.json`: signed, permanent reproduction maps for removed shards;
- `arm64_wheel_resolution_receipt.json`: a signed, payload-free map of the
  exact CPython 3.12 Linux ARM64 wheel set resolved from the pinned lean
  requirements, including transitive versions, filenames, target tags, sizes,
  and SHA-256 hashes. This receipt is produced on demand by
  `resolve_h2_arm64_wheels.py`, not by the recurring storage guardian, so a
  package-index outage cannot interrupt scientific execution;
- `windows_atomic_publication_policy.json`: a checksum-bound map of the
  operational-only Windows retry shim, its exact launcher hash, bounded delay
  schedule, and scientific boundary. Its compact event log is kept under
  `<workspace>\logs\windows_atomic_publication_events.jsonl`;
- `compression_receipts\*.json`: signed records of any active long-session
  directory armed for inherited lossless NTFS compression, including exact
  job/path identity, unchanged logical inventory, command result, scientific
  boundary, and reversal command;
- `storage_forecast.json`: current free space and a conservative next-job peak
  derived from the complete frozen job manifest, including future queues;
- `artifact_lifecycle.json`: a signed compact map of what is retained, when its
  last planned consumer occurs, what can be regenerated, and which receipt or
  checksum inventory reproduces removed payloads;
- `last_guardian_pass.json`: actions and safe refusals from the latest pass;
- `guardian.lock`: an operating-system byte lock preventing duplicate guardians.

The preserved v13 workspace also contains
`lossless_ntfs_compression_receipt.json`. It records the separate, completed
lossless compression of inactive v8 and v10 workspaces, including pre/post key
hash verification and the exact compression logs. Those workspaces remain
fully readable and can be decompressed with `compact.exe /U`; no logical bytes
were deleted.

`lossless_ntfs_compression_supplement_20260827.json` records a later bounded
compression pass over stopped v1. It was deliberately ended when concurrent
disk-read latency became visible: 140 files covering 1.64 GB of logical data
were compressed and all key hashes remained exact; v11 and v5 were left
untouched. This is the intended priority—never trade active scientific
throughput for optional background compaction when projected capacity is safe.

The process also emits one JSON event per relevant action to standard output.
Redirect standard output and error to the workspace log folder for unattended
operation.

The forecast reserves the largest observed future single-job peak before it
classifies storage risk. `OK` means that projected peak still leaves at least
80 GiB free. `EARLY_RECLAIM` means it remains above the controller's 35 GiB
corruption-prevention reserve but inactive storage should be reclaimed.
`CRITICAL_RECLAIM` means the projected H2 peak itself could reach the hard
reserve. The lifecycle map avoids duplicating huge inventories: authoritative
result `checksums.json` files and signed prune receipts remain the exact maps.

The forecast deliberately continues to use logical bytes after compression;
it does not assume an optimistic compression ratio. Consequently its displayed
peak remains a conservative warning even after the protection is armed.

Whole-job peak projection prefers checksum-validated, sealed complete-job
receipts and applies a 1.5× safety factor. Before the first result seal, partial
live rates provide the fallback projection. Once sealed evidence exists, the
guardian no longer rewalks active case-shard trees: those live measurements
cannot change the sealed projection basis, and repeatedly inventorying them can
compete with model imports and worker startup on Windows. Exact C: free space is
still measured on every pass. This preserves capacity protection while keeping
the guardian lightweight during active inference.

The guardian also skips a full historical result checksum index when every
completed job already has a signed prune receipt (or has no restart-shard tree).
It rebuilds that index automatically as soon as a newly sealed shard tree is
eligible for validated pruning. The optimization changes only when redundant
inventories run; it does not relax any deletion or checksum gate.

## Anaconda Prompt or PowerShell

Open Anaconda Prompt or PowerShell and enter:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'

$Workspace = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17'
$Results = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17'

C:\Users\amiri\anaconda3\python.exe .\scripts\maintain_h2_storage.py --workspace $Workspace --results-root $Results --once --dry-run
```

Review the `would_prune` events. To perform one validated maintenance pass:

```powershell
C:\Users\amiri\anaconda3\python.exe .\scripts\maintain_h2_storage.py --workspace $Workspace --results-root $Results --once
```

To follow the campaign automatically until it reaches a terminal state:

```powershell
C:\Users\amiri\anaconda3\python.exe .\scripts\maintain_h2_storage.py --workspace $Workspace --results-root $Results --follow --interval-seconds 300 --minimum-free-gib 35 --target-free-gib 80
```

The repository wrapper uses the same project Python environment and appends
each launch to durable logs:

```powershell
.\scripts\run_h2_storage_guardian.ps1 -Workspace $Workspace -ResultsRoot $Results -IntervalSeconds 300 -MinimumFreeGiB 35 -TargetFreeGiB 80
```

The normal safe-capacity cadence is five minutes so maintenance does not
continually compete with model workers. If the forecast changes to
`EARLY_RECLAIM` or `CRITICAL_RECLAIM`, the guardian automatically tightens its
cadence to at most 60 seconds until capacity is safe again. A failed maintenance
pass is also retried within 60 seconds.

`supervise_h2_product_program.ps1` now detects the controller in either its
direct `python -m app.h2_product_program` form or through the hardened
`h2_windows_atomic_retry_bootstrap.py` wrapper. It also recognizes the
checksum-bound `h2_prefreeze_selector_correction_bootstrap.py` continuation.
When the unmodified controller naturally reaches the audited Phase-5 selector
failure, the supervisor runs the correction launcher's read-only fail-closed
preflight. It starts that continuation only when the staged launcher proves the
exact protocol, completed development results, failure signature, released
campaign lock, unopened held-out boundary, and immutable staging hashes. A
non-eligible preflight falls through to the normal bounded recovery path. This
handoff changes orchestration only: it does not alter model inference,
thresholds, completed results, or the prepared runtime implementation identity.
Use `-DisableSelectorCorrection` only for diagnosis.

To exercise the supervisor's exact read-only preflight call path without
launching or changing the campaign, run:

```powershell
.\scripts\supervise_h2_product_program.ps1 -SelectorCorrectionPreflightOnly
```

While a scientific job owns the campaign lock, the expected result is
`NOT_ELIGIBLE`, exit code 3 from the bound launcher, and
`ActiveCampaignWasModified: false`. At the audited safe boundary it reports
`ELIGIBLE`; the continuously running supervisor then performs the launch.

The supervisor also detects this storage
wrapper or a directly launched guardian for the exact workspace. It starts the
guardian when absent and checks both processes throughout controller
supervision, so an operational exit is recovered without changing scientific
state. The current controller and guardian can still be launched independently;
their locks prevent duplicate execution and duplicate storage maintenance.

The Windows process inventory is restricted at the WMI query itself to the
Python and PowerShell executable families that can own these helpers. This
avoids a slow or wedged full-system `Win32_Process` enumeration delaying
supervisor recovery while retaining the exact command-line and workspace
identity checks. The final-package watcher lookup in the controller launcher is
likewise restricted to PowerShell processes.

The supervisor also recognizes one bounded, non-scientific ReDimNet recovery:
an evaluation-enrollment worker that is still alive but does not republish its
ready message within the frozen 90-second reload window. Resume keeps sealed
case shards and content-addressed cache entries, so this recovery does not
discard completed work or alter the scientific runtime identity. The match is
deliberately exact and remains subject to the consecutive-recovery limit.

Recovery accounting is based on genuinely consecutive failures. After a
relaunched controller has remained alive for ten minutes **and** the durable
campaign progress identity advances, both recovery counters reset. Isolated
Windows publication failures hours apart therefore cannot exhaust a lifetime
counter. A process exit without a recognized signature receives at most two
bounded restart-safe attempts while the program remains nonterminal. A durable
`stop_request.json`, `STOPPED`, `BLOCKED_*`, or final completion state is never
restarted, and repeated unclassified exits stop for diagnosis rather than
hiding a deterministic failure. Recognized and unclassified exits also share
the overall consecutive-recovery ceiling, so alternating error types cannot
bypass it. Supervisor JSON reads use Windows
read/write/delete sharing so observation does not obstruct atomic publication.

If the controller's 35 GiB corruption-prevention reserve is nevertheless
reached, the supervisor treats that as a safe storage pause rather than a
terminal campaign failure. It keeps the guardian alive, waits without starting
new cases until C: recovers to the configured 80 GiB target, and then launches
the normal checksum-validating `Resume -RetryFailed` path. This wait has no time
limit. It cannot create space consumed by unrelated applications, but it
prevents H2 from filling C: and avoids a manual campaign restart after H2 space
has been reclaimed.

The 35 GiB value matches the controller's current hard reserve. The 80 GiB
guardian target is an advisory early-warning level; it does not impose a time
limit and does not stop the scientific campaign.

To launch controller recovery and storage recovery together after a machine or
process restart:

```powershell
.\scripts\supervise_h2_product_program.ps1
```

The supervisor launches child processes with hidden windows and writes events
to `<workspace>\logs\controller.supervisor.jsonl`. It resumes from the
transactional campaign state.

### Persist the active v17 campaign across Windows logon

`register_h2_v17_scheduled_tasks.ps1` creates five current-user, limited-
permission logon tasks for the active v17 campaign: the controller/storage
supervisor, milestone notifier, serial-resource host-I/O audit, post-campaign
quiet-resource/UI-latency helper, and final-package watcher. It uses `IgnoreNew`,
allows battery operation, has no execution
time limit, and retries an unexpected helper exit three times at one-minute
intervals. It never starts or retunes a scientific job itself; each helper uses
the campaign's existing locks, frozen v17 paths, and transactional resume.

Preview the exact inputs and commands without changing Task Scheduler:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\register_h2_v17_scheduled_tasks.ps1
```

Register and verify the tasks:

```powershell
.\scripts\register_h2_v17_scheduled_tasks.ps1 -Apply
```

No Anaconda environment or Python command is needed; this installer runs in
Windows PowerShell. Inputs are the fixed v17 workspace, results root, summary
root, config, and current Windows user. Its output is both console JSON and
`automated_runs\h2_complete_product_pipeline_v17\storage_maintenance\scheduled_tasks_v17.json`.
That receipt records the exact actions, installer hash, user, and whether the
superseded v16 helpers were disabled. It does not delete or reinterpret v16
evidence. Use `-KeepSupersededV16Enabled` only for a deliberate historical
operation; the normal v17 install disables those old logon helpers to prevent a
superseded campaign from restarting alongside v17.
When present, the final-package augmenter validates the receipt against the
terminal workspace/results/summary paths and packaged installer hash, then
includes it as `reproducibility/storage/scheduled_tasks_v17.json`.

Historically, four equivalent v16 tasks were registered. They are retained as
disabled Task Scheduler records after the v17 installer runs; they do not
change configurations, thresholds, datasets, metrics, or result hashes:

- `JustPeachy H2 v16 Supervisor`
- `JustPeachy H2 v16 Milestone Notifier`
- `JustPeachy H2 v16 Serial Resource Audit`
- `JustPeachy H2 v16 Final Package Watcher`

Task Scheduler uses `IgnoreNew` single-instance behavior, allows execution on
battery power, does not impose an execution time limit, and retries an
unexpected task failure three times at one-minute intervals. The tasks run only
after this Windows user logs on; they are not a machine-wide service and do not
contain credentials. The visible read-only monitor remains an operator window
and is intentionally not auto-opened at every logon.

Inspect the registered task definitions and their last-run state:

```powershell
$taskNames = @(
    'JustPeachy H2 v16 Supervisor',
    'JustPeachy H2 v16 Milestone Notifier',
    'JustPeachy H2 v16 Serial Resource Audit',
    'JustPeachy H2 v16 Final Package Watcher'
)
Get-ScheduledTask -TaskName $taskNames |
    Get-ScheduledTaskInfo |
    Format-Table TaskName, LastRunTime, LastTaskResult, NextRunTime
```

Disable the restart helpers without changing or stopping the scientific
campaign already in memory:

```powershell
$taskNames = @(
    'JustPeachy H2 v16 Supervisor',
    'JustPeachy H2 v16 Milestone Notifier',
    'JustPeachy H2 v16 Serial Resource Audit',
    'JustPeachy H2 v16 Final Package Watcher'
)
$taskNames | ForEach-Object { Disable-ScheduledTask -TaskName $_ }
```

Remove only these startup registrations after the final package has validated:

```powershell
$taskNames = @(
    'JustPeachy H2 v16 Supervisor',
    'JustPeachy H2 v16 Milestone Notifier',
    'JustPeachy H2 v16 Serial Resource Audit',
    'JustPeachy H2 v16 Final Package Watcher'
)
$taskNames | ForEach-Object {
    Unregister-ScheduledTask -TaskName $_ -Confirm:$false
}
```

Active long-session compression is enabled by default on Windows. For a
diagnostic run where it must be disabled, append
`--disable-active-long-session-compression`. Do not use that switch for the
unattended campaign unless adequate free space has independently been reserved.

## Windows Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
set "H2_WORKSPACE=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17"
set "H2_RESULTS=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17"
C:\Users\amiri\anaconda3\python.exe scripts\maintain_h2_storage.py --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --once --dry-run
```

## Safety and recovery behavior

- A failed check produces `refused`; the suspect bytes remain untouched.
- Running, partial, failed, stopped, or incomplete jobs are never eligible.
- The only exception to the preceding deletion rule is non-destructive NTFS
  metadata on a running long-session shard directory: its files are retained,
  its logical content is unchanged, and the action is signed and reversible.
- Ordinary accuracy jobs and every `measurement_mode=resources` job are never
  compressed by this guardian.
- If power is lost after removal but before the final receipt is committed, the
  next pass verifies the signed pending receipt and completes the receipt.
- If a final receipt exists, later passes validate it and do nothing.
- Shared content-addressed inference cache entries remain through their last
  neural consumer because development, held-out, streaming, reliability, and
  resource jobs reuse them. After the program is terminal they are marked for
  ownership review, not blindly deleted, because the cache is shared with
  other campaigns.
- Preflight bytecode and the workspace-level
  `<workspace>\private_biometric_cache\` restart cache are excluded from the
  final public package. Their exact locations, retention classes, and final
  cleanup boundary are recorded in `artifact_lifecycle.json`.
- The script does not promise protection against unrelated programs filling C:.
  Its forecast makes that risk visible while avoiding duplicate H2 growth. If
  another program consumes the reserve, H2 waits safely and resumes only after
  the configured target is restored.

## Final reproducibility package

The final-package watcher waits for a terminal guardian pass after the
controller reaches `COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`. The augmented compact
ZIP then includes the signed lifecycle, final forecast/pass, the signed ARM64
wheel-resolution map, every prune and v14 compression receipt, all
post-selection dynamic-execution bindings, this guide, the guardian/supervisor
source, and the focused tests. The package validator
rechecks both receipt signatures and the nested pre-prune validation signatures.
It also preserves the native ZIP's pre-publication controller state unchanged
and adds the exact terminal workspace `program_state.json` as a separate,
checksummed member. Immutable program, protocol, workspace, results, and summary
bindings must match across the two snapshots. This records the publication-time
state transition without rewriting any native scientific package member.

The removed restart shard payloads are not copied into the ZIP. Raw audio,
model weights, shared caches, and private biometric caches are also excluded.
Their governed external locations and exact reproduction identities remain in
the frozen manifests, result inventories, and storage receipts.

The ZIP also includes and validates the Windows atomic-publication policy,
event log, launcher, and run instructions. These explain recovered Windows
sharing violations without treating retries as scientific measurements or
retaining duplicate payloads.

The ARM64 receipt similarly does not retain or package wheel payloads. It binds
the exact requirements file, frozen runtime identity, platform/ABI tags, and
every resolved wheel hash. Recreate a wheelhouse only when ARM64 validation or
offline installation is imminent, then discard it again after its target-side
validation receipt is sealed.

## Monitoring

Keep using the normal campaign monitor in a separate PowerShell window:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\monitor_h2_product_program.ps1 -Follow -IntervalSeconds 30
```

The monitor reads the guardian output and shows the storage risk, conservative
largest-job peak, projected free space after that peak, and guardian timestamp.
It remains read-only with respect to all scientific state.

Inspect the storage forecast at:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17\storage_maintenance\storage_forecast.json
```
