# Compact complete current-release discovery V5

Use V4's purpose, paths, inputs, CLI and namespace regression instructions in
[README_CURRENT_BACKUP_SCOPE_V4.md](README_CURRENT_BACKUP_SCOPE_V4.md), replacing
the action with `discover_production_backup_action_v5.py` and operation label with
a fresh `production-scope-05` (PowerShell, CMD and Anaconda Prompt alike).

V4 completed the read-only walk but the enclosing inspector rejected its large
JSON result at the unchanged 262,144-byte stdout limit. Its natural failure and
exact process closure are retained. V5 retains every selected file path/size,
root, absence proof, metadata SHA and explicit historical exclusion. It omits
duplicated embedded profile/RELEASE bodies, per-file preliminary stat identities,
and repeated prose. Campaign/desktop listings become count+canonical SHA; every
selected shortcut remains in the complete file list. The subsequent backup
independently obtains and checks actual identities and hashes under its leases.

The v2 compact result encodes each complete member as root_index/relative/bytes; paths reconstruct uniquely and losslessly. prepare_production_scope_v3.py strictly decodes once. It has an 80,000-byte bound inside the unchanged inspector
limit. `hashes_verified:false` still means the discovery is not a file-hash
backup. Source model pins remain separately verified evidence. No selected
member, referenced gallery or missing-root error is omitted to fit the bound.

Native command from this directory, after exact backup and compile review:

```powershell
& $PY -B ./host_operations.py --label production-scope-05 --action ./discover_production_backup_action_v5.py --payload FRESH_PAYLOAD.json
```

```bat
"%PY%" -B host_operations.py --label production-scope-05 --action discover_production_backup_action_v5.py --payload FRESH_PAYLOAD.json
```

Inputs and output are otherwise V4's. No file is changed on the Pi. Never reuse
an operation label or treat discovery as `COMPLETE` backup certification.
