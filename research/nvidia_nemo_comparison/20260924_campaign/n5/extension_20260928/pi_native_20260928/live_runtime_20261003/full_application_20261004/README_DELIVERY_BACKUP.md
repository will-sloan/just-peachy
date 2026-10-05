# Restored-release backup

Purpose: preserve the actual restored build21, immediate build17 rollback, sole
desktop shortcut and complete current user data/configuration alongside the
previous selected rc5/v27/v28/gallery roots. Inputs are actual closed runtime,
fresh boot/expiry and measured full-copy allowance; outputs are complete scope,
hash-pinned locked source snapshot and independently verified private PC copy.
It is a selected-release backup, not a copy of every old research root.

`prepare_full_asset_inventory.py` prepares `inventory_full_assets_action_v1.py`
by changing only the expected package from build08 to build21. It independently
backs up/restores the action and keeps the original 60-second, 4GiB total,
1GiB-per-file streaming hash limits. Run this read-only action through host driver
v9 with fresh boot/expiry and the build21 manifest before preparing the backup.
The previous selected-assets receipt belongs to an earlier boot and is invalid
for this backup. Inputs are exact package/manifest/current boot; output is a
same-boot asset hash inventory, with no model loading or native payload writes.

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\prepare_full_asset_inventory.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\host_full_operations_v9.py --label UNIQUE-ASSETS-LABEL --action .\inventory_full_assets_action_v1.py --payload 'FRESH-BUILD21-ASSET-PAYLOAD.json'
```

CMD and Anaconda Prompt use the same executable/arguments without `&`.

PowerShell, from this directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\prepare_full_backup_discovery.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\host_full_operations_v9.py --label UNIQUE-SCOPE-LABEL --action .\discover_full_backup_action_v1.py --payload 'FRESH-BOOT-EXPIRY.json'
```

CMD / Anaconda Prompt: the same explicit Python executable and arguments in
double quotes, omitting `&`. No environment activation or download is needed.

The preparer backs up/restores both source versions and reviews that only
`discover` changes. Original4096-file/64-root/2MiB census limits stay. After a
successful complete discovery, use `prepare_production_scope_v3.py`,
`launch_backup_external_action_v2.py` through host driver v9, and
`reconcile_production_backup_external_v5.py` exactly as documented in the parent
`README_BACKUP_EXTERNAL_V2.md` / `README_PRODUCTION_SCOPE_V3.md`. Use new labels,
the actual build21 manifest and source-derived full allocation. PC seed files
must independently match the native hash before reuse; missing/changed members
are streamed. All source bytes remain on the Pi. A failed census/transfer never
authorizes silently omitting files, deleting data or claiming COMPLETE.

The old scope preparer assumes all eleven pre-consolidation desktop shortcuts
still exist and correctly rejects the new one-shortcut discovery. Preserve that
failure. Use `prepare_restored_backup_scope.py` with exactly the same arguments
as `prepare_production_scope_v3.py` instead. It requires the literal build21
package/manifest and exactly the observed sole Just Peachy desktop entry before
binding that catalogue to the original complete-scope preparer. All membership,
missing-root, asset, full-allocation, historical-exclusion and time checks stay.
Run it with the same explicit PowerShell/CMD/Anaconda Python command; output and
subsequent native backup launch is unchanged; PC reconciliation uses V5 as documented in the parent README_BACKUP_RECONCILER_V5.md. V2 incorrectly parses native POSIX scope paths with Windows Path and its failed backup06 attempt is retained.
