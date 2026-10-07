# One unified Desktop shortcut and explicit all11 restore

Purpose: complete the existing one-file production activation by archiving the
other ten exact retained v28 shortcuts outside Desktop. `install_candidate`
replaces one selected shortcut only; it never removed the other ten. This
external action closes that gap without editing retained package sources,
recordings, galleries or startup configuration. It starts no application.

`desktop_consolidation_action.py` runs only through the existing guarded
`host_operations.py` dispatcher. Inputs are an actual production package and
manifest SHA, the selected original Desktop filename, its actual activation
backup/plan, the newly activated shortcut SHA, fresh current boot/expiry and a
new archive path. The literal11filename/size/SHA pins come from actual
post-soak-baseline02; there is no wildcard removal. Qualification packages fail
the production gate. Its accepted full-backup manifest must contain all11
original Desktop files and the exact disabled autostart/start-prototype files.
All must be copied backup bytes, not external model references.

Before removal, it makes two independent fsynced/read-back copies of every
original shortcut. The selected original comes from the already verified
activation backup; the other ten come from current Desktop bytes. It also
preserves two copies of the new unified launcher. All native output stays in
the separately reserved16MiB archive above the5GiB floor. Full Desktop
membership is bounded at128entries, regular files at1MiB, and is checked
before and after. Unexpected symlinks/edited owned files fail closed.

The ten exact other files are moved only after every backup succeeds and the
full Desktop census remains equal. Each move has a durable intent. The result
must contain exactly one of the11owned names with its new unified bytes, plus
all unrelated entries unchanged. Autostart remains disabled, the retained270°
desktop remains, and application Exit-to-desktop behavior is unchanged.

`mode="restore"` explicitly restores all11original shortcuts after checking
the exact consolidated membership and both restore copies. It preserves the
new unified launcher in the archive. It never replaces an edited/unrelated
file. A failed or interrupted multi-file operation leaves its partial state,
intents and copies intact for a separately reviewed recovery; it does not
pretend a group of filesystem renames is atomic or automatically retry.

## Inputs and commands

First follow `README_DESKTOP_ACTIVATION.md` through successful production
activation and independent copy/readback. Construct a reviewed private JSON
payload using actual returned values (expiry is a JSON number):

```json
{
  "mode": "consolidate",
  "boot_id": "<actual current boot>",
  "expires_unix": 0,
  "maximum_output_bytes": 16777216,
  "package": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-NN",
  "package_manifest_sha256": "<production manifest SHA256>",
  "selected": "<one of the11actual retained Desktop filenames>",
  "activation_backup": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-desktop-backup-<activation UUID>",
  "expected_current_sha256": "<ACTIVATION_PLAN next_sha256>",
  "archive": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-desktop-consolidation-<fresh32hex UUID>"
}
```

PowerShell (inside the documented CPU14/early-owner host workflow):

```powershell
& $py -B "$n/host_operations.py" --label desktop-consolidation-01 --action "$n/desktop_consolidation_action.py" --payload "$q/reviewed-desktop-consolidation.json" --writes
```

Command Prompt or Anaconda Prompt, same qualified interpreter; no install or
environment activation is needed:

```bat
"%PY%" -B "%N%/host_operations.py" --label desktop-consolidation-01 --action "%N%/desktop_consolidation_action.py" --payload "%Q%/reviewed-desktop-consolidation.json" --writes
```

Use `PY=C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe`.
`N` is the current runtime source directory and `Q` its private evidence root,
as defined in `README_STORAGE.md`. Host operations registers its own CPU14
owner before project reads and reserves independent PC output capacity.

For explicit rollback, create a fresh payload with `mode="restore"`, the same
package/manifest/archive and fresh boot/deadline, then run the same commands
with label `desktop-consolidation-restore-01`. Do not run the older one-file
rollback first: this restore returns all11 originals, including the selected
launcher. No restored application starts automatically.

Outputs: host operation receipts plus the native archive's `PLAN.json`,
`before/`, `restore/`, `archived/`, unified launcher copies, move intents and
`CONSOLIDATED.json` or explicit `RESTORED.json`. Preserve their independent PC
copy and final member/hash readback through the full-backup reconciliation
workflow before calling the operation complete. Current code preparation and
host tests do not claim native consolidation, native restore or boot proof.

Host tests: use the CPU14 early-owner wrapper in `README_STORAGE.md` with
`test_desktop_consolidation`. They exercise actual11baseline pins against
private temporary fixtures, archive/restore readbacks, changed source refusal,
copy-failure isolation, and edited restore/unrelated-file refusal. No Pi calls.
