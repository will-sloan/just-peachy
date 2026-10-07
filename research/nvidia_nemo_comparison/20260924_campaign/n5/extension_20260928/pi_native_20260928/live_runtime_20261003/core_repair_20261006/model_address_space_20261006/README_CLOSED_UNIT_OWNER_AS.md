# Extended closed ownership receipt admission

Purpose: let the host dispatcher admit a completely copied, independently closed
build33 top-level GUI/hour supervisor receipt containing actual AS/stack/kind
facts. `closed_unit_owner_as.py` is a standard-library host adapter, not a native
action or runtime change. Status: prepared source only, unexecuted. Build33's
actual accepted manifest hash must be supplied by the dispatcher after sealing.

Inputs: the unchanged `host_operations_v6.closed_unit_owner` callback, the actual
accepted build33 manifest SHA256, and the existing `(job, raw, entry, closure)`
arguments. Output: the same `{sha256, owner}` pin, bound to original mirrored
receipt bytes. It writes nothing and does not inspect or signal a process.

The existing old form is passed directly to its original validator. The new
form has exactly four additional fields: `address_space`, `stack`,
`qualification_kind`, `recording_model_scope`. Integers/bools are checked by exact
type; stack remains `[1048576,1048576]`. Integrated `full_app_hour` and the exact
modern live/saved GUI job require `[1073741824,1073741824]` and true model scope.
Other shared-wrapper kinds require `[805306368,805306368]` and false scope.
Modern GUI additionally binds the original two V2 helper hashes and actual
NATIVE_CHECK path. The hour keeps 3600 source seconds and 4680 owned seconds.

Before projecting out the new fields, the adapter verifies the original complete
mirror member bytes/hash and exact accepted package. It then invokes the
unchanged old validator on a local old-form representation to retain every
actual job/closure/owner/lifetime/raw-admission check. Only the returned receipt
hash is restored to the original immutable member hash. This projection never
rewrites a receipt or adds a JOB. Historical nested idle, backup and watchdog
decoder key sets remain untouched.

## Dispatcher integration and commands

Root's separately reviewed V10 dispatcher must hash-bind and independently
backup/restore this source and this README before loading the standard-library
adapter. At its existing driver hook, bind the *actual accepted* build33 pin:

```python
prior_closed_unit_owner = driver.closed_unit_owner
driver.closed_unit_owner = adapter.make_closed_unit_owner_validator(
    prior_closed_unit_owner, actual_accepted_build33_manifest_sha256)
```

The same reviewed hook can perform the focused pure checks once before binding:

```python
checks = adapter.selfcheck_closed_unit_owner(
    prior_closed_unit_owner, actual_accepted_build33_manifest_sha256,
    legacy_case=actual_immutable_legacy_case,
    hour_case=actual_immutable_hour05_case,
    gui_case=actual_immutable_live47_case)
```

Each case has exactly `job`, `raw` (original receipt bytes), `entry` (mirror
member), `closure`. The root driver must verify complete mirrored source pins
before passing them. The helper first admits all original cases through the old
callback. Its ten checks include old-form passthrough, local extended hour/GUI
views, and seven malformed-field/type/kind/stack/hash/package rejections. New
fields/PIN in these two local views are synthetic test inputs only; original
jobs/receipts are not changed or written. The small returned metadata reports
that actual new native enforcement is unproven. Root can write that check result
in its existing registered host review receipt; no additional campaign or model
runner is required. No checks have run for this prepared source.

Do not invoke a native action or run a Python process merely to import this
library. The coordinated CPU14 V10 `--host-review` command is the eventual
source/admission review entry; actual native dispatch remains a separate root
operation. V10 must exist, be source-reviewed and bind the actual33 hash first.

PowerShell, source inspection (no Python or native action):

```powershell
$a='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/model_address_space_20261006'
Get-FileHash -Algorithm SHA256 "$a/closed_unit_owner_as.py"
Get-FileHash -Algorithm SHA256 "$a/README_CLOSED_UNIT_OWNER_AS.md"
```

Command Prompt and Anaconda Prompt, source inspection:

```bat
set "JP_AS=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\model_address_space_20261006"
certutil -hashfile "%JP_AS%\closed_unit_owner_as.py" SHA256
certutil -hashfile "%JP_AS%\README_CLOSED_UNIT_OWNER_AS.md" SHA256
```

After Root authorizes one registered host slot and seals V10's source/pins, the
review command in either Command Prompt or Anaconda Prompt is:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "ACTUAL_REVIEWED_V10_DISPATCHER_PATH" --host-review
```

PowerShell uses `& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B 'ACTUAL_REVIEWED_V10_DISPATCHER_PATH' --host-review`.
No conda installation, model load or download is needed. Update this README when
actual source-review/closure and mirrored build33 results exist; none are claimed
by this prepared adapter.
