# Current release backup and preserved historical inventory

`discover_production_backup_action_v3.py` prepares the current release/data scope.
The preceding read-only V2 found106 roots because it included every old research
profile/gallery directory. V3 does not expand the64-root or4096-file bounds and
does not delete, mutate, or claim a new backup of those historical campaign roots.

The selected scope includes v27/v28 source/control/backups, both current profile
directories, every E0/E1 gallery referenced by their actual bounded descriptors
(even an older gallery), their exact policy-named recording roots and any newer
operator recording beyond their reserved range. Complete current data/config,
the actual selected rc5 source, selector, startup, display and11desktop entries
are retained. Missing referenced data blocks preparation. Uncreated policy slots
need the existing exact UNUSED/RESERVED-only proof and later native rechecks.

All other discovered historical operator/profile/gallery roots remain in the
output as `historical_roots_preserved_outside_copy`, with explicit exclusion
reason and `new_backup_claimed:false`. Their original native directories and
earlier private backups are preserved. The complete106-root V2 receipt remains
immutable. This is selected-release-and-user-data backup, not a newly verified
copy of the entire historical research campaign. No new actor may write to an
excluded root as part of activation or rollback.

Inputs: fresh actual boot_id and numeric expires_unix within600seconds. Outputs:
the existing read-only host operation RESULT.action_result, complete current
membership/extents, actual policy/profile metadata pins, explicit missing-slot
proofs and unchanged historical-root classification. File contents are hashed
and independently copied only by the later locked backup workflow described in
README_BACKUP_EXTERNAL.md. The action holds the normal exclusion leases, starts
no capture/model, and is not an admission or completed backup.

PowerShell (the exact qualified existing environment; no installation):

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
& $PY -B "$N/test_current_backup_scope.py" --output-root "$Q"
& $PY -B "$N/host_operations.py" --label production-scope-03 --action "$N/discover_production_backup_action_v3.py" --payload 'ACTUAL_FRESH_PAYLOAD.json'
```

Command Prompt and Anaconda Prompt use the same PY/N/Q paths and arguments:

```bat
"%PY%" -B "%N%\test_current_backup_scope.py" --output-root "%Q%"
"%PY%" -B "%N%\host_operations.py" --label production-scope-03 --action "%N%\discover_production_backup_action_v3.py" --payload "ACTUAL_FRESH_PAYLOAD.json"
```

Fill the real reviewed payload path; do not pass --writes. Run native discovery
only when prior owned work and its mirror have closed. The focused host checker
registers CPU14 and actual owner before project reads, independently backs up
and restores the three source/documentation files, and checks current references,
new recordings, older referenced galleries and missing-data refusal in isolated
fixtures. Synthetic checks do not prove current native membership or backup.
