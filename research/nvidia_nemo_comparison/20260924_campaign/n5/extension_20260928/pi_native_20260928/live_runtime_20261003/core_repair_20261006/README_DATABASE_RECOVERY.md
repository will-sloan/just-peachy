# Core database recovery

Purpose: inspect normal SQLite hot-journal recovery on exact backup copies,
then provide a separately admitted native action for the original database.
These tools never delete a recording, manually remove a journal, use an
`immutable` SQLite URI, import the new `SessionStore`, upgrade the schema or print
caption text, enrollment vectors or audio contents.

`core_database_recovery.py` supplies bounded raw SQLite primitives. Inputs are
the captured database/journal census entries and real source/copy directories.
Outputs are independent byte/hash readback, normal `BEGIN IMMEDIATE`/`ROLLBACK`
recovery, `quick_check(1)`, exact before/after sidecar extents/hashes and at most
16 recent session IDs/statuses/counts. Cache size is 2 MiB and the progress guard
expires after at most 30 seconds. An `audio_discarded` flag is reported only if
actually stored as a boolean in `sessions.spec`; its absence is not inferred.
Partial Discard candidates require a census-verified, owned explicit stored
deletion intent. Legacy `discarded` status and orphaned files alone do not grant
deletion authority. These outputs are inspection evidence only.

`recover_core_database_copy.py` is the Windows host-copy CLI. It registers CPU14
before project imports and accepts a census path, exact census SHA256, backup
payload root and a fresh private output directory. Before any SQLite connection,
it verifies both PC database and hot-journal extents/hashes against the census,
makes an unrecovered copy and a separately verified independent restore, and
opens only the restore. The original PC copies and census must remain unchanged.
Source code backup/readback, owner, copy verification, result and process-return
receipts are preserved. The caller verifies actual process closure separately.
The output explicitly certifies only the copied files; it never claims that an
unfinished whole backup is complete. It requires the existing C50/G75-GiB host
floors with room for two exact copies, bounded receipts and a 120-second scope.

Run only in the allocated CPU14 host slot after other registered Python owners
are closed. Do not run a native/model/SSH task from this CLI. PowerShell:

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$backupDir = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/production-backup-11-reconcile-01'
Set-Location -LiteralPath $repairDir
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' recover_core_database_copy.py --census "$backupDir/CENSUS.json" --census-sha256 7167f6db5e50f18937a995904fea3aacec717a127c4431a82bfa66788e10a3a2 --payload-root "$backupDir/payload" --output 'G:/PRIVATE-EXISTING-PARENT/FRESH-DB-REPAIR'
```

CMD or Anaconda Prompt using the existing interpreter, without installing packages:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006
set BACKUP_DIR=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\production-backup-11-reconcile-01
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe recover_core_database_copy.py --census %BACKUP_DIR%\CENSUS.json --census-sha256 7167f6db5e50f18937a995904fea3aacec717a127c4431a82bfa66788e10a3a2 --payload-root %BACKUP_DIR%\payload --output G:\PRIVATE-EXISTING-PARENT\FRESH-DB-REPAIR
```

Replace the output with a new child under a real private existing parent. Never
reuse a prior output or replace a failed attempt. The census pin above belongs
to the named captured backup, not a future snapshot.

`recover_core_database.py` is the separate native action. Its stdin schema is
`just-peachy.core-database-recovery.v1`. Mandatory payload fields are `schema`,
`package`, `package_manifest_sha256`, `boot_id`, `expires_unix`, `database_source`
(both original complete census entries), `maximum_file_bytes`,
`original_db_recovery: true`, `accepted_full_backup` and `driver_guard`.

`accepted_full_backup` contains pinned native copies of the completed backup's
`census_path`/`census_sha256`, `manifest_path`/`manifest_sha256`,
`complete_path`/`complete_sha256`, and `scope_path`/`scope_sha256`. Their actual
contents must agree on all members/counts/bytes, independent readback, unchanged
source and all five original aliases: package, runtime-data, desktop, autostart
and display configuration. A selected-session backup cannot authorize this step.
`driver_guard` binds `boot_id`, `pid_baseline_sha256`,
`pid_baseline_verified: true`, `no_active_project_handles: true`, and
`research_and_hardware_exclusive: true`. The root action driver performs and
retains the actual fresh process/handle/lease checks; the helper does not acquire
those leases a second time.

The helper verifies its own/library package source pins, exact current boot,
short-lived authority, original file identities/hashes and the FSIZE admission
before SQLite opens. It uses CPU3, 128 MiB address space, 1 MiB stack and a
30-second alarm. `maximum_file_bytes` must equal actual filesystem capacity less
5 GiB, with the same physical free-space reserve. The parent driver must already
admit this exact action and capacity-derived hard FSIZE; an older 32 MiB hard
limit cannot recover this 35,889,152-byte database. Output is bounded JSON OWNER,
RECOVERY_ADMITTED and RESULT records with metadata and exact sidecars.

Do not run this native file from Windows/Anaconda, or through an ad hoc SSH
command. The host dispatcher must first accept the completed whole backup,
review the host-copy result, bind the exact native source SHA/schema/capacity and
fresh guard proof, then execute the separately admitted native job. No native
action is authorized by merely running the host-copy CLI. Keep this README
updated whenever payload fields, source pins, run commands or recovery scope
change.

Validation on 2026-10-06: the census-bound host copy recovery passed in
`audit-preparation/core-database-copy-recovery-20261006-4cf710c9393243208088135cb0d691e4`
under the private local live-runtime directory. CPU14 owner PID 56608,
creation FILETIME 134357795517036550, returned naturally with exit 0 and was
independently confirmed absent. Source backup and independent source restore
were exact. Both original PC database/journal files and the census stayed
unchanged. Normal SQLite recovery changed only the independent restore's
database and removed that restore's hot journal; `quick_check(1)` returned `ok`.
The recent 16 metadata rows contained no census-verified explicit deletion
intent and no stored `audio_discarded` boolean. No recording was deleted, no
native action was run, and the pending whole backup was not certified.
