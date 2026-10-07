# Reviewed immutable build33 preparation

`build_event_package33.py` prepares a source review and, only after root approval
of that exact review, a new immutable build33 package from sealed build32. This
is host-only packaging code. It does not execute runtime/model code, SSH,
capture, change shared recordings/galleries, stage a Pi package, activate a
desktop, publish source, or qualify a native result. Build32 was sealed but was
never native-staged. The actual desktop baseline remains build30.

## Purpose and selected source scope

Closed build31 hour05 failed at 922.9 source seconds with a compact-event
`MemoryError()` and contemporaneous D1 backlog pressure. The original allocation
line and ordering relative to `backlog_stop` are unproven. The source-bound
768 MiB model address-space ceiling was nearly exhausted while physical RAM
remained available. This candidate combines two narrow changes for a fresh
qualification; the historical failed hour remains a failure.

Exactly seven package replacements are admitted:

* This directory's `event_compaction.py`, `runtime_support.py` and paired
  `README_EVENT_WRITER_STREAMING.md`. Actual registered HOST14 matched exact
  compact-record bytes, logical digests and FIFO behavior, and reduced traced
  preparation peak without a measured CPU regression. The C JSON fast path
  remains; selected immutable bytes are admitted as one complete queue item.
* Sibling `model_address_space_20261006/worker.py`, `native_scope.py`,
  `launch_raw_qualification_action.py` and paired `README_MODEL_ADDRESS_SPACE.md`.
  Actual registered HOST10 must verify the exact source/AST/reverse-transform
  scope and finite role-specific address-space constants before preparation is
  admitted. Until that proof exists, the builder rejects execution.

The candidate changes the finite model worker ceiling from 768 MiB to 1 GiB.
Its frontend retains a 256 MiB soft limit with a 1 GiB model-capable hard limit;
the independent outside metadata scope remains 128 MiB. The action's independent
parent is 1 GiB only for `full_app_hour` and the modern `classic_driver.py`
Live/Saved ReDimNet/TitaNet recording scope. Other qualification/reference
parents retain 768 MiB. Physical free-RAM floors, stack/CPU/core/task guards,
storage reserves, source/owner checks and session/drain/backlog settings remain.
The source constants are authority; no new product tunable or BINDING key is
introduced. `model_address_space_policy` is explicit review/provenance metadata.

All other build32 gallery capacity code and build31 caption identity code are
preserved. No model, asset, backend descriptor, gallery data, recording or raw
source/proof byte changes. Only exact target/reference/profile path and
pin/content/provenance control derivatives are permitted. The existing BINDING
and production acceptance limits structure remains.

## Exact inputs and outputs

The parent package is campaign-local
`audit-preparation/gallery-package32-d1140c29f0d843c881bd719309bb5d6d/package`,
manifest SHA256
`55f449d563b3011a0793cef174921a215cd9aeb0dbbaa597b228ae4ba889fbbf`.
The target is
`/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-33`.
The protected raw source remains SHA256
`84f40eb404049164ec7efdaf27668e0a54044b5a874323f779237148e75768bf`.
Its four qualification proof files retain their complete byte contents; only
the BINDING proof location is translated to build33.

The original immutable packaging core is the live-runtime root's
`ui_restore_20261004/build_classic_package.py`, SHA256
`bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5`.
The exact source inventory helper is the sealed build32 preparer
`../capacity_gallery_20261006/build_gallery_package32.py`, SHA256
`7f30a1a15631698630888fbf93fb0711197f1e3d820695b54a76528f358021d2`.
Only its pure AST/function/import inventory helpers are used; its main/build
functions are never called. The original packaging core inventory, output,
archive admission and independent whole-member restoration are reused.

CLI inputs:

* `--host-test-root`: the actual successful HOST14 writer root, including
  registered owner, source backup/restore proof, repeated unchanged pins,
  successful result and independent exact-owner closure. This result is pinned
  to SHA256
  `11d11396ac5bf239bdac983646e3d01369b624a54b6c57b277a2b0c9bbf4c337`.
  Its read-only codec reference is frozen build31; the builder proves those two
  codec origins remain exactly the same in the sealed build32 parent.
* `--address-space-test-root`: the actual successful HOST10 proof from the
  sibling model-address-space checker. All three runtime and two check/runner
  files must match the tested current bytes. The exact accepted result is
  SHA256 `ae873cdb69385ee3c8fa7918ddc20221a8871f356c06162fdf9b62eead857bcf`.
  All 445 full-parent/draft/preserved source pins and 890 backup/restore files
  are rechecked using the actual AS proof's fields. Drive-relative, rooted,
  escaping or aliased preservation tokens are rejected. A prepared/proposed source root,
  failed receipt or unclosed owner cannot substitute for this proof.
* `--review-only`: emit the full source/AST/import inventory without a package.
* Actual build additionally requires `--review-manifest`, `--review-sha256`
  and `--reviewer` matching the root-reviewed emitted review exactly.

Both host roots must be ordinary existing directories under the campaign-local
`audit-preparation` parent. All runtime/check sources, paired current READMEs,
core/inventory helpers and actual proof receipts are independently backed up
and restored/read back before deriving a package. Current READMEs are pinned
separately, allowing evidence-only updates after their registered checks close.

Five exact accepted hour05 receipts are read only: worker RESULT/ENVELOPE,
compaction receipt, external mirror completion and UNIT_OWNERSHIP. Their hashes
are pinned in source. Only hashes, numeric writer counts and explicit failed
scope enter the public package provenance; no caption text or private audio is
read by the builder. Full receipt backups stay in the private host preparation
root. The actual old ENVELOPE/UNIT_OWNERSHIP represent their historical unit;
new runtime effective AS must later be read from fresh native worker/owner
receipts, rather than inferred from the existence of this host package.

Every invocation creates a fresh `event-package33-<UUID>` private host root and
registers CPU14/PID/creation FILETIME before any project read. Review output:
`REGISTERED_OWNER.json`, `HOST_SCOPE.json`, source backups/restores,
`PREPARED_SOURCE_CLOSED.json`, `SOURCE_DIFF_REVIEW.json`, `SOURCE_CLOSED.json`.
The review uses `just-peachy.event-writer-model-as-package-source-review.v1`.
It inventories every changed/added/removed function, module-scope AST, source
pin and reachable package import, and binds both actual host results and the
failed hour evidence. No native result is relabelled.

After exact root approval, build output additionally includes `package/`,
`field-runtime-v29-build-33-prepared.tar.gz`, `BUILD_RESULT.json` and
`BUILD32_MEMBER_PRESERVATION.json`. That preservation receipt enumerates the
only allowed changed/additional members and rejects removals or any untouched
runtime/asset difference. The package manifest is a separate derived control.
Source backup/restore twins within the package carry exact current replacement
bytes as the pinned historical core requires. The complete immutable parent
package remains separate, and provenance binds its prior member hashes. The
original finite 8 MiB package, 2 MiB
compressed archive and 512 member admission bounds remain. A post-build
independent host process check and whole-archive/member restore proof remain
required before any stage preparation.

## PowerShell review, then separately approved build

These commands are templates. Obtain one host slot from the root coordinator.
The builder has no default native action and cannot be used to skip proof or
approval. Use the existing project interpreter, not WindowsApps `python`.

```powershell
$taskRoot = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/event_writer_streaming_20261006'
$pythonPath = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$auditRoot = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation'
$writerProof = Join-Path $auditRoot 'event-writer-host-649e50fbed2a45d1865aefae87f80b3f'
$addressProof = Join-Path $auditRoot 'model-as-host-5fbd3e2486f34d37b6e058ecf83f778b'
& $pythonPath -B (Join-Path $taskRoot 'build_event_package33.py') --review-only --host-test-root $writerProof --address-space-test-root $addressProof
$reviewExit = $LASTEXITCODE
if ($reviewExit -ne 0) { throw 'Preserve failed preparation; do not build' }
```

The final JSON line names the fresh review root and emitted SHA. Independently
check the registered PID/FILETIME and natural exit, rehash all source pins and
backup/restore pairs, and record exact owner closure. Root reviews that exact
inventory before the following separate invocation:

```powershell
$reviewPath = 'REPLACE_WITH_ACTUAL_ROOT_REVIEWED_SOURCE_DIFF_REVIEW.json'
$reviewSha = 'REPLACE_WITH_ROOT_APPROVED_64_HEX_SHA256'
& $pythonPath -B (Join-Path $taskRoot 'build_event_package33.py') --host-test-root $writerProof --address-space-test-root $addressProof --review-manifest $reviewPath --review-sha256 $reviewSha --reviewer 'REPLACE_WITH_ACTUAL_ROOT_REVIEWER'
$buildExit = $LASTEXITCODE
if ($buildExit -ne 0) { throw 'Preserve failed package/evidence; do not stage' }
```

The current source/proof inventory must still equal the approved manifest,
including its source paths and hashes. There is no reuse of an old approval or
old native PASS. Keep earlier partial roots and use fresh labels for retries.
The root's registered host wrapper adds independent `INDEPENDENT_CLOSURE.json`
only after natural return, exact owner absence, every current input/backup/
restore equality, full tar member readback and independent restored bytes are
verified. A preparer's `SOURCE_CLOSED.json` alone is not that process proof.

## Command Prompt and Anaconda Prompt

No installation or environment update is required. Run the explicit existing
interpreter from either prompt; a conda activation is not needed.

```cmd
set "JP_EVENT_TASK=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\event_writer_streaming_20261006"
set "JP_WRITER_PROOF=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\event-writer-host-649e50fbed2a45d1865aefae87f80b3f"
set "JP_AS_PROOF=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\model-as-host-5fbd3e2486f34d37b6e058ecf83f778b"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%JP_EVENT_TASK%\build_event_package33.py" --review-only --host-test-root "%JP_WRITER_PROOF%" --address-space-test-root "%JP_AS_PROOF%"
echo %ERRORLEVEL%
```

After the same independent closure and root source review, supply the exact
approved review and reviewer as in the PowerShell build example. No command in
this README stages a native package or starts a healthy model campaign.

## Current status and native handoff

Writer HOST14 passed and is independently closed; its four code inputs remain
frozen. Model AS HOST10 passed with zero failures/errors/skips; PID 37044,
creation FILETIME 134357928742504775, returned naturally with exit 0 and was
independently confirmed absent. Its result is pinned above and independent
`HOST_CLOSED.json` is SHA256
`0c5d430b60d69d1bf9b11d60140f258867c3e225706f79a3181b92506731c9e7`.
All three runtime and two check/runner files retain their tested bytes; current
paired documentation is separately pinned after evidence updates.
This builder/README are source-only preparation; no
build33 review or package has yet run. After a reviewed sealed33, a fresh ops
adapter must require target33 Live49/Saved50, sustained hour06 and complete
closed independent mirrors. Final activation must use the actual prior
build30 desktop compare-and-swap, rather than a nonexistent build32 desktop.
Any exact measured payload allowance is a separate reviewed dispatcher change;
this builder does not broaden native utility caps or stage permissions.
