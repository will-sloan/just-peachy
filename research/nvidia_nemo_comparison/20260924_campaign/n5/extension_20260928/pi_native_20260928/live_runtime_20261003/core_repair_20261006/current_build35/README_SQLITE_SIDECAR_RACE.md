# SQLite sidecar concurrency candidate

This separate iteration prepares a possible build30 repair for the build29
filesystem admission failure observed in native check37. The candidate changes
only `storage_support.py`; build29 source and package remain immutable. It is
source-only runtime candidate; root authorized the focused host check, which
passed as recorded below. A new package still requires root's source review.

## Evidence and purpose

Root reported native check37 (CurrentDelayed with ReDimNet, the same 60.4-second
source used by passing checks35/36) failing around 53 seconds with
`ValueError: Regular single-link SQLite files required`. The wrapper traceback
does not identify the file, file mode, or link count. An unlinked rollback journal
is a plausible explanation, not yet a confirmed observation of this failure.
Worker evidence must settle the offending database path and available stat facts.

Root's subsequent read-only inspection found `history.sqlite3` regular,
single-link, 42,061,824 bytes, inode440635, with all three sidecars absent. The
failed launch's worker result had `failure=null`, `cleanup_error=null`, and
`logical_cleanup_complete=true`. The failure was reported through the UI/store
reader while the worker later stopped successfully. The old error carries no
offending suffix or stat snapshot, so these facts cannot prove the earlier inode
or link count. Inspection receipt:
`Q/operation-core-guard37-inspect-01/dispatch/RESULT.json`, where Q is the local
live-runtime evidence root used in the commands below. Failed native check37
remains retained in `Q/classic-ui-check-37-monitor-01`.

The frozen helper first inspected paths with `lstat`, then used a separate
following `stat` and rejected all link counts other than one. Linux reports
`st_nlink` as the hard-link count. SQLite DELETE journaling removes the rollback
journal at commit. A lookup already resolving an inode can overlap that unlink.
References: [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html),
[SQLite temporary files](https://www.sqlite.org/tempfiles.html),
[Linux inode metadata](https://man7.org/linux/man-pages/man7/inode.7.html),
[Linux unlink](https://man7.org/linux/man-pages/man2/unlink.2.html).

The candidate final lookup uses non-following `lstat`. Only a **regular named
SQLite sidecar** (`-journal`, `-wal`, or `-shm`) observed with zero links receives
one further read-only `lstat`. An absent name is a completed unlink and contributes
zero current bytes. A different inode with an ordinary single-link regular file
is a replacement sidecar and contributes the greater of old and new observed
sizes. Replacement acceptance requires nonzero inode identifiers. A still
anomalous inode, the same inode relinked, an unknown inode identifier, a main
database zero-link observation, hard links, symlinks, reparse points, and
nonregular files fail with path/mode/link/device/inode/size diagnostics. Only
`FileNotFoundError` receives absence handling; permission and other lookup errors
propagate. The guard never deletes or opens a journal for recovery.

The one-recheck boundary is deliberate: a second zero-link inode or a same-inode
observation still fails. This handles one completed unlink or validated
replacement, not unlimited journal churn. Parent-directory checks remain metadata
observations rather than atomic path/open protection; existing store ownership
and canonical-root enforcement are still required. Independent caption-agent
static review found no unsafe acceptance in this intended inspection boundary.

All capacity calculations, the physical reserve, basename validation, SQLite
metadata allowance, and finite Linux RLIMIT_FSIZE handling retain build29 logic.
The existing 8 MiB writable-admission floor above reserve still applies. This
candidate adds neither a corpus quota nor a recording-count limit.

Frozen source pin:
`../storage_support.py` SHA256
`296996fb689ee7eb89f462d8ee563fb84477765e458a806a6257140836ae964c`.
The registered runner checks this pin before importing candidate tests.

## Code, inputs, and outputs

- `storage_support.py`: same public `sqlite_file_size_plan`,
  `ensure_sqlite_file_limit`, `error_facts`, and `annotate_error` APIs as build29.
  Inputs are the storage root, reserve policy, nonnegative metadata allowance,
  and validated database basename. Output is the existing capacity plan or a
  detailed filesystem exception. The inspection helper writes no files.
- `test_sqlite_sidecar_race.py`: 17 focused temporary-fixture tests. Inputs are
  deterministic stat observations plus isolated SQLite files. It covers ordinary
  disappearance/replacement, bounded retry, main-file rejection, actual hard
  links, symlink/reparse/nonregular rejection, permission propagation, retained
  journal bytes, unchanged capacity admission, and overlapping real SQLite
  DELETE-mode transactions. A deterministic fixture confirms that the frozen
  build29 guard rejects the zero-link observation while the candidate handles
  the subsequent completed unlink. The real transaction fixture verifies all 120
  updates and `quick_check`; it does not claim to reproduce the native nlink0
  observation on Windows.
- `run_host_sidecar_checks.py`: one Windows CPU14 process. Required input
  `--output` is a fresh nonexistent private directory whose parent exists. It
  writes registered owner/scope receipts before project imports, five source
  backups and independent restores, bounded test output, source-closure pins,
  `RESULT.json`, `HOST_EXIT.json`, and an empty closed fixture directory. Receipts
  are independently read back; sources must remain unchanged. Host safety is
  120 seconds, 32 MiB output admission, 64 KiB log, C: 50 GiB and G: 75 GiB free
  floors. These bound a test's working set, not recordings. Root independently
  verifies exact PID/creation-FILETIME absence after natural exit before
  releasing the host slot.

## Run from PowerShell

Coordinate a free root-approved host slot before any rerun. The command uses the
existing project Python directly and registers
CPU14 inside the runner; it starts no subprocess, SSH, model, or native action.

```powershell
$iteration = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/sqlite_sidecar_race_20261006'
$receipt = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/core-sidecar-host-' + [guid]::NewGuid().ToString('N')
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' (Join-Path $iteration 'run_host_sidecar_checks.py') --output $receipt
Get-Content -LiteralPath (Join-Path $receipt 'RESULT.json')
Get-Content -LiteralPath (Join-Path $receipt 'REGISTERED_OWNER.json')
```

## Run from CMD or Anaconda Prompt

Use the same existing interpreter; activating an Anaconda environment is not
required. Replace `REPLACE_WITH_FRESH_LABEL` with a unique unused label and check
that the audit-preparation parent exists. Do not run concurrently without root's
host-slot coordination.

```bat
set "ITERATION=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/sqlite_sidecar_race_20261006"
set "RECEIPT=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/core-sidecar-host-REPLACE_WITH_FRESH_LABEL"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" "%ITERATION%/run_host_sidecar_checks.py" --output "%RECEIPT%"
type "%RECEIPT%/RESULT.json"
type "%RECEIPT%/REGISTERED_OWNER.json"
```

## Current disposition

Final focused host check: **PASS, 17 tests, zero errors/failures/skips**, 0.656
seconds. All five source backups and independent restores read back unchanged;
the temporary fixture directory was empty. Exact CPU14 owner PID26244,
creation FILETIME134357830840231905, returned naturally with code0 and was
independently absent. Receipt:
`Q/audit-preparation/core-sidecar-host-20261006-5e647c63cb7440a7a575db2e3e0ee92a`
(`RESULT.json`, `SOURCE_CLOSED.json`, `HOST_EXIT.json`, `HOST_CLOSED.json`).

An earlier 17-test run failed from two fixture defects: connection context
managers did not explicitly close SQLite handles before Windows cleanup, and a
spy incorrectly forbade `Path.lstat`'s internal `stat(follow_symlinks=False)`.
Those test defects were corrected; the candidate runtime helper was unchanged.
Its natural code1 owner PID27876/FILETIME134357830495157965 is independently
closed. Its failure, source snapshots, and tiny temporary synthetic database are
retained unchanged at
`Q/audit-preparation/core-sidecar-host-20261006-1ef80890790343a3ab3949b959254eb4`.

No native run, build30 package, staging, activation, or publication has been
performed by this iteration. Root must
review the narrow change and evidence before the new immutable build can be
prepared. Native check37 remains a retained failure. Passing prior checks35/36
do not qualify this candidate, and successful synthetic fixtures cannot establish
the original native inode/link-count facts. Update this README with actual test
receipts and subsequent native outcomes as they become available.
