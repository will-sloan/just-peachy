# Current-release backup through a separate pinned helper

This derivative copies the selected current release and current user data. It
preserves immutable08, earlier helper sources, discovery01's refusal and
discovery02's complete106-root inventory. It does not claim a new backup of the
whole research campaign. Root-owned read-only V3 discovery selects actualrc5,
v27/v28 source/control/backups, their actual profile and referenced gallery roots,
named recording roots and newer operator roots, all current data/config, and
the exact11 owned shortcuts plus startup/display files.

`backup_external_common_v2.py` adds only the two exact directory roots
`/home/peachyprototype/JustPeachy/data` and `/home/peachyprototype/JustPeachy/config`
to the previous rc5 helper. Their complete descendant membership is still
walked and hashed. The campaign parent, install parent, unrelated siblings,
symlinks, multiple links, unsafe paths and changed source membership remain
refused. Bounds stay64 roots,4096 files,2 MiB census. The rc5 selector and the
two startup file pins remain unchanged. Explicit absence proofs remain limited
to actual empty or exact reserved-never-started v27/v28 slots and are rechecked
before and after the locked native census.

The exact external helper is20,433 bytes, SHA256
`aba044705f9e4938261cd82d46264b5c4868206abcac290a31580f971a1d50ef`,
schema `just-peachy.external-backup-common.v2`. The action and native probe
derivation both require that literal source. The host dispatcher must also have
the separately reviewed V2 action/schema/size/hash/base64 gate before dispatch;
the V1 gate does not authorize this derivative. No native command was executed
while preparing these files.

`prepare_production_scope_v2.py` consumes the complete actual V3 discovery JSON
and actual `selected-assets-01.json` object, including its
`actual_hashes_verified:true` and matching boot ID. It explicitly maps `resolved`
to `resolved_path`. Only canonical, individually pinned immutable weights inside
the selected copy roots may reduce copied bytes. Other in-scope assets remain
copied. Assets outside those roots remain separately verified references; they
do not reduce this backup reservation or claim a new guard verification/copy.
The original asset receipt, input hash, each asset classification and complete
historical exclusion inventory are retained. Historical research roots outside
copy remain unchanged; earlier private backup references and the separate closed
GUI recording mirror/export must be retained independently. A current-scope
COMPLETE receipt is never a whole-campaign COMPLETE claim.

## Inputs and outputs

Inputs: actual locked discovery, actual same-boot selected asset evidence,
explicit full-copy byte reservation and180–3600second native snapshot lifetime,
exact admitted package/manifest pin, fresh production-backup-NN label, and
reviewed local seed mappings. Scope preparation emits SCOPE/PAYLOAD, all input
backups and independent restore copies, and PREPARATION. It performs no SSH.

`launch_backup_external_action_v2.py` verifies the immutable package and stages
the exact helper in a fresh evidence directory. `backup_external_protocol_v2.py`
derives the existing probe at its exact reviewed boundaries.
`reconcile_production_backup_external_v2.py` reuses the existing missing-only
streamed transfer, exact active guard gate, independently hashed PC seed copies,
source before/after census, ordinary complete closed mirror and final independent
readback. It retains the source OWNER/unit/lease proof and compatible MANIFEST,
COMPLETE and FULL_BACKUP receipts. Failure preserves source and evidence and
never emits successful completion.16 MiB metadata/preparation allocation is
separate from the full-copy allocation; PC C:50 GiB/G:75 GiB and native5 GiB
floors remain in force.

## PowerShell

Use fresh reviewed labels/paths and actual byte/lifetime values. The commands
below are templates for the root operator after existing user authorization and
fresh admission. Do not run during another native job. The scripts publish their
actual early CPU14 PC owner before project/data access.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
# Set $allocation, $seconds, $package, $manifest and $packageCopy from reviewed current evidence.
& $py -B "$n/prepare_production_scope_v2.py" --discovery "$q/operation-production-scope-03/dispatch/RESULT.json" --external-model-pins "$q/selected-assets-01.json" --maximum-payload-bytes $allocation --runtime-seconds $seconds --output "$q/production-scope-03-preparation" --package $package --package-manifest-sha256 $manifest --label production-backup-01
& $py -B "$n/host_operations.py" --label production-backup-01 --action "$n/launch_backup_external_action_v2.py" --payload "$q/production-scope-03-preparation/PAYLOAD.json" --writes
# Save the returned actual action_result as production-backup-01-JOB.json.
& $py -B "$n/reconcile_production_backup_external_v2.py" --job "$q/production-backup-01-JOB.json" --package-copy $packageCopy --seeds "$q/reviewed-current-backup-seeds.json" --output "$q/production-backup-01-reconcile-01"
```

## Command Prompt or Anaconda Prompt

Run `powershell -NoProfile` and use the same complete block. The exact interpreter
above needs no environment activation or installation. Seed mapping format is
in README_PRODUCTION_BACKUP.md; map aliases from actual SCOPE only. A candidate
seed is accepted only after its current bytes/hash match the native census.

For host-only focused checks, use the CPU14 early-owner test wrapper in
README_STORAGE.md with `test_backup_external_v2`. The tests cover the actual08
wrapper/probe anchors, exact helper source pin, unchanged rc5/startup constraints,
the two directory-root additions and sibling refusal, and selected asset/current
scope classification. They make no native completeness or transfer claim.
