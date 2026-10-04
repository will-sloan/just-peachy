# Current-release backup discovery V4

This read-only discovery preserves v27/v28 and their explicitly referenced data,
galleries, selected installed release, current data/config, startup and shortcuts.
Historical campaign roots are inventoried as preserved outside this particular
copy. It does not modify a gallery, recording, release, or desktop entry.

V3 rejected actual E0-only descriptors. V4 accepts the observed E0-only or E0+E1
namespace sets and requires E1 when the actual selection uses TitaNet. No missing
referenced root becomes a successful backup. The 64-root/4096-file/2 MiB discovery
bounds remain. The checker reads all 20 retained v27/v28 descriptor bytes and
rejects missing TitaNet, unknown namespaces, schema and type errors.

Inputs: retained private profile copies for the host regression; a fresh JSON
payload containing actual `boot_id` and finite `expires_unix` for native read-only
discovery. Outputs: unique host source backups, independent restores and review;
native scope membership, exclusions and missing-root/unused-slot facts. Discovery
is not a complete backup certificate. The separate V2 backup workflow must copy,
independently verify and close its guard before activation.

PowerShell, from this directory:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$B='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928'
& $PY -B ./check_current_scope_v4.py --private $B
& $PY -B ./host_operations.py --label production-scope-04 --action ./discover_production_backup_action_v4.py --payload FRESH_PAYLOAD.json
```

CMD or Anaconda Prompt, from this directory (use the pinned existing environment):

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "B=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928"
"%PY%" -B check_current_scope_v4.py --private "%B%"
"%PY%" -B host_operations.py --label production-scope-04 --action discover_production_backup_action_v4.py --payload FRESH_PAYLOAD.json
```

Every operation label must be unused. Never replay a consumed discovery label.
The host dispatcher checks all ownership, capture, resource and strict SSH guards.
