# Injected database recovery preparation

Purpose: adapt raw hot-journal recovery to the root driver's actual injected
`PAYLOAD`/`BASELINE` action contract, without changing build28 or the preserved
standalone v1 draft. The tested `core_database_recovery.py` library is supplied
as SHA-bound base64, compiled in memory after root's early native owner. The
action defines `RESULT`; it does not read stdin, dispatch SSH, install sources,
import SessionStore, delete a recording, or manually clear a sidecar.

`prepare_core_database_recovery_v2.py` runs only in an allocated Windows CPU14
host slot. Inputs: actual completed full PC backup directory; exact census,
manifest, COMPLETE and canonical scope SHA pins; existing immutable package
directory and manifest pin; successful copied-database recovery RESULT and
SHA; current observed boot UUID; observed actual filesystem total minus 5 GiB;
and a fresh private output directory. It requires normal exact native backup
owner/cgroup closure and rehashes every full payload member with exact membership
before creating a compact certificate. A selected-file recovery receipt alone
cannot create that certificate. Outputs: registered owner, exact source backups
and independent restores, HOST_CERTIFICATE, fresh PAYLOAD, RESULT and HOST_EXIT.
No native admission or dispatch occurs. Preserve independent OS process closure.

PowerShell, after full backup completion and host-slot allocation:

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
Set-Location -LiteralPath $repairDir
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' prepare_core_database_recovery_v2.py --backup-root 'ACTUAL_COMPLETE_BACKUP' --census-sha256 ACTUAL_CENSUS_SHA --manifest-sha256 ACTUAL_MANIFEST_SHA --complete-sha256 ACTUAL_COMPLETE_SHA --scope-sha256 ACTUAL_CANONICAL_SCOPE_SHA --package 'ACTUAL_HOST_PACKAGE' --package-manifest-sha256 ACTUAL_PACKAGE_SHA --copy-result 'ACTUAL_COPY_RESULT.json' --copy-result-sha256 ACTUAL_COPY_RESULT_SHA --boot-id ACTUAL_CURRENT_BOOT_UUID --maximum-file-bytes ACTUAL_FILESYSTEM_TOTAL_MINUS_5GIB --output 'ACTUAL_PRIVATE_EXISTING_PARENT/FRESH_RECOVERY_PREPARATION'
```

CMD and Anaconda Prompt use the existing interpreter without package installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe prepare_core_database_recovery_v2.py --backup-root ACTUAL_COMPLETE_BACKUP --census-sha256 ACTUAL_CENSUS_SHA --manifest-sha256 ACTUAL_MANIFEST_SHA --complete-sha256 ACTUAL_COMPLETE_SHA --scope-sha256 ACTUAL_CANONICAL_SCOPE_SHA --package ACTUAL_HOST_PACKAGE --package-manifest-sha256 ACTUAL_PACKAGE_SHA --copy-result ACTUAL_COPY_RESULT.json --copy-result-sha256 ACTUAL_COPY_RESULT_SHA --boot-id ACTUAL_CURRENT_BOOT_UUID --maximum-file-bytes ACTUAL_FILESYSTEM_TOTAL_MINUS_5GIB --output ACTUAL_PRIVATE_EXISTING_PARENT\FRESH_RECOVERY_PREPARATION
```

Replace each `ACTUAL_...` value with captured evidence; never invent a boot,
recording, hash, capacity or completion. Output must be a new directory. Prepare
and dispatch sequentially because the payload expires in 290 seconds.

`recover_core_database_v2.py` is a native injected action, never a host CLI.
Schema: `just-peachy.core-database-recovery.v2`. Payload fields: schema, package,
package_manifest_sha256, boot_id, expires_unix, original_db_recovery:true,
database_source (two complete original census entries), maximum_file_bytes,
accepted_full_backup, accepted_full_backup_sha256, library_source_b64,
library_source_sha256. The canonical compact host certificate schema is
`just-peachy.full-backup-host-certificate.v1`; it includes the four full-backup
proof SHA pins, exact total files/bytes, five scope roots, exact database pair,
and successful whole completion, independent payload readback, source before/
after verification and native backup closure flags. The root sealed action
driver binds and preserves that actual host evidence.

Native execution requires the root's exact action/schema/SHA admission,
capacity-derived initial hard FSIZE, CPU3/128 MiB address space/1 MiB stack and
early owner. The action rechecks current boot, package pin, exact original pair
identities/hashes, capacity and 5 GiB free reserve. It checks BASELINE owners/
free_leases and holds existing research, hardware, launcher and active-store
locks nonblocking through SQLite recovery. Current project data/sound handles
reject the action. Cache is 2 MiB and SQLite progress/alarm scope is 30 seconds.
It returns exact before/after sidecars and recent noncontent session metadata.
Only pair metadata is supplied natively; it certifies no deletion intent and
performs no Discard. Original recording deletion remains a separate action.

Validation: the shared raw recovery library passed exact copied-database
hot-journal recovery and `quick_check=ok`; original PC copies stayed unchanged.
This injected adaptation and host certificate preparation are prepared only,
with native execution and completed-full-backup admission pending. Keep these
commands, schema fields, evidence limits and validation status updated.

The root agent selected a simpler path after preparation: preserve these
standalone/injected drafts as PREPARED and UNEXECUTED, then let build29's normal
SessionStore open recover the journal under its capacity guard during the live
UI validation. No separate recovery/certificate preparation process has run,
and no separate native maintenance action is planned by this task. The exact
copied-database PASS remains the recovery-library evidence.
