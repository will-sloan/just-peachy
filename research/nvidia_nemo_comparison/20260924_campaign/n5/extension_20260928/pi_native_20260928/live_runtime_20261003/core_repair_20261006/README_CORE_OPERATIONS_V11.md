# Core dispatcher V11

Purpose: dispatch root-reviewed host/native operations while preserving the immutable V10 preread, historical owner/lifetime/closure checks, metadata utility resource guard and native operation authority. This source-only derivative does not qualify model quality, run models, or authorize an operation by itself.

V11 executes the exact SHA-bound V10 source prefix before `bind_extended_closed_owner()`. It omits that previously passing ten-case review on each invocation. The unchanged SHA-bound `model_address_space_20261006/closed_unit_owner_as.py` still enforces actual original mirrored bytes, AS/stack/kind/scope, the exact two modern live/saved helper hashes, and every legacy callback check. Six small synthetic routing checks prove only historical passthrough, build33/build34 selection, and unknown/malformed/duplicate rejection. Synthetic checks create no JOB or native result.

Extended receipts select the immutable validator using the actual accepted JOB pin: build33 `2889a2bd...` or build34 `fb9ca638...`. Unknown or malformed extended receipts fail. Old receipts go to the original validator, including historical strict nested idle receipts.

All operations retain the original 2 MiB payload ceiling. The existing exact sealed stage33 exception remains. Only `core-stage34-01`, `--writes`, and a byte-for-byte matching reviewed certificate/payload/action/archive/installer/inventory/reservation can receive 3 MiB. No generic increased payload limit exists. The accepted boot and backup14 pins, CPU14 early registration, free-space floors, finite metadata helper limits, native owner/lifetime/lease guards and operation-specific limits remain.

Inputs: original dispatcher CLI options (run `--help` only when root authorizes an invocation), exact action/PAYLOAD files, and optional paired `--stage34-admission ABSOLUTE_PATH --stage34-admission-sha256 LOWERCASE_SHA256`. Both new options are removed before the unchanged original argparse handles all other arguments. No certificate means no oversized34 stage admission. The supplied certificate must exactly equal the frozen actual stage34 constants; its explicitly reviewed SHA binds its original bytes. An operator-written certificate with guessed future hashes is rejected.

Certificate keys are exactly:

```text
schema = just-peachy.core-stage34-root-admission.v1
label = core-stage34-01
manifest_sha256 = fb9ca63814906629ec9e93935f4d28e77d1c60e1f6202f212223116195a0e802
parent_manifest_sha256 = 2889a2bddc9b6cb65c150510e87db978eb5fb24e4ffa22809b1623d45234b61e
target = /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-34
expected_boot_id = e60e67c2-f3f5-4b8b-8eab-2613df2de37e
payload_sha256 = e150e52129c395bf83897b6821574a685c56fdd21503dc4e9071ce9fa6b65996
payload_bytes = 2291501
action_sha256 = 4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74
installer_source_sha256 = b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6
archive_sha256 = 5a4e83bf7b9bbe3874b363e7af842b706ddecc8150f7676874c7c7d003a36ce1
archive_bytes = 1703894
source_review_sha256 = 53275087e72069b6d3012f505616079ab8debaa90a290848f1830e159e9c6096
members = 447; expanded_bytes = 7492370; directories = 8; target_reservation_bytes = 9851624
accepted_backup_metadata_sha256 = {COMPLETE.json:9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e, RESULT.json:1154c795a07e35941d21f99fc81617f0534dd3de51771c070d031ce526d2f879, CENSUS.json:509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263}
```

The certificate is strict JSON (duplicate keys/nonfinite values rejected), <=16 KiB, ordinary single-link canonical file. Positive actual counts reject booleans. Payload must exceed2 MiB but remain <=3 MiB; archive remains <=2 MiB, installer <=128 KiB. The immutable installer’s pure validator independently expands and hashes canonical members; computed reservation must match the certificate and PAYLOAD. Neither normal runtime limits nor product logical capacities change.

Outputs: fresh CPU14 registration and source backup/independent restore directories under private `Q/audit-preparation`; inherited dispatcher receipts; `OWNER_FAMILY_ROUTING_CHECK.json`, `V11_SOURCE_BINDING.json`, and (only exact oversized34 stage) `STAGE34_PAYLOAD_ADMISSION.json`. Root independently checks exact host closure after execution. The source is PREPARED, UNEXECUTED until root approval; no native outcome is claimed here.

The fixed certificate is `CORE_STAGE34_ROOT_ADMISSION.json` beside this source, 1,362 bytes, SHA256 `3808827ccba4d7560e8d9f1a3e655caf542dd440c848c309b8df3d69fb6d93f6`. It contains only reviewed source pins, not a native result. Root verifies its SHA and the actual stage directory `Q/audit-preparation/core-performance-stage34-preparation-3604a00549544230ab2ac6bbaf2d6c65` before invocation. The exact fresh stage command follows; execution belongs to root.

PowerShell:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$prep='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/core-performance-stage34-preparation-3604a00549544230ab2ac6bbaf2d6c65'
$cert="$d/CORE_STAGE34_ROOT_ADMISSION.json"
$certSha='3808827ccba4d7560e8d9f1a3e655caf542dd440c848c309b8df3d69fb6d93f6'
& $py -B "$d/host_core_operations_v11.py" --stage34-admission $cert --stage34-admission-sha256 $certSha --label core-stage34-01 --action "$prep/ACTION.py" --payload "$prep/PAYLOAD.json" --writes
```

Command Prompt and Anaconda Prompt (use the pinned interpreter; no conda install or activation required):

```bat
set "D=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PREP=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\core-performance-stage34-preparation-3604a00549544230ab2ac6bbaf2d6c65"
"%PY%" -B "%D%\host_core_operations_v11.py" --stage34-admission "%D%\CORE_STAGE34_ROOT_ADMISSION.json" --stage34-admission-sha256 3808827ccba4d7560e8d9f1a3e655caf542dd440c848c309b8df3d69fb6d93f6 --label core-stage34-01 --action "%PREP%\ACTION.py" --payload "%PREP%\PAYLOAD.json" --writes
```

For all nonstage operations omit the two certificate options; accepted33/34 owner routing remains available. Keep original action/PAYLOAD/preparer sources and all failed/closed receipts unchanged. Frozen V10 and the owner adapter are never edited by V11. Root handles native execution; source preparation is host-only.
