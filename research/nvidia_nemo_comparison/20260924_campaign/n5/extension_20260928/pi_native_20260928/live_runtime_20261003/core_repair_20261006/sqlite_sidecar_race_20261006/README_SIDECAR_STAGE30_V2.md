# Build30 staging preparation

`prepare_sidecar_stage30_v2.py` prepares a reviewed host payload for the existing
stage-only installer. It consumes the accepted immutable build30 output and
completed production-backup13 metadata. It performs host preparation only;
native staging is a separate guarded root action. It imports no runtime/model,
opens no SQLite store, and starts no capture or SSH. These preparer files are
technical procedure sources, not frozen runtime package replacements.

## Exact inputs and ancestry

Immediate derivative parent is `../prepare_core_stage29_v2.py`, SHA256
`8b0bc5a35da080b5077b2b96c59ab516f20cf1278014df897526c36b5394fc17`.
It is preserved and independently backed/restored along with the historical
stage28 preparer SHA256
`5025c86eab988737f31fc1616b10cb003f136dec943b057778fecdb1447fa359`.
The unchanged installer SHA256 is
`b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6`;
the unchanged native action SHA256 is
`4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74`.

Q is
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003`.

| Input | Exact value |
| --- | --- |
| Build output | `Q/audit-preparation/sidecar-package30-99ab101518ce402a9a2c8d5f6ac96cc6` |
| New target | `/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-30` |
| Shared user data | `/home/peachyprototype/JustPeachy/data/runtime-v29` |
| Build30 manifest | `b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569` |
| Build30 archive | `652e2321bd56b1eb3c51ade34d4f13d1218281b827bd2c955d90a7ae7f1f5f6f` |
| Root-approved source review | `337cfff9ac688ee947b66e2920306dbca5c11a72fd230486ad35eec54bfd34c7` |
| Package's exact build29 parent | `331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b` |
| Backup13 selected rollback build28 | `e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b` |

Package ancestry and backup selection are distinct. Build30 derives from
immutable29; backup13 preserves the selected desktop rollback28 together with
the current changed shared user-data tree. The preparer requires that exact
backup28 job pin, not the package parent's29 pin.

Root accepted the source review and authorized the actual build. Build30 passed,
natural0, exact PID61940/creation FILETIME134357833475437829 independently absent.
There are420 declared members plus manifest; all421 were independently rehashed
after archive restore. The only runtime change is the selected helper plus new
README;412 parent members remain identical, seven permitted helper/control
members changed, one README added, none removed. Ten source/evidence inputs and
their independent backups/restores matched. `INDEPENDENT_CLOSURE.json` retains
an incidental PowerShell count-array in `source_inputs`; individual source pins
and successful per-input readbacks are authoritative, with a separate correctly
counted supplemental readback recorded alongside the immutable receipt.

## Backup prerequisite

The only prerequisite location is `Q/production-backup-13-reconcile-01`.
Root must accept its actual completed `COMPLETE.json` and `RESULT.json` SHA256
pins before invocation. The initial backup13 census covered2,870 files and
677,122,259 bytes; transfer was active when this source was prepared. Progress,
a census, or a reusable-byte report is not a completion. The guard requires
actual selected-release/user-data COMPLETE, all-regular-output mirror, source
before/after verification, external asset pins, canonical restoration roots,
exact backup13 job/invocation/current boot, natural0, exact owner absence and
empty cgroup. The accepted metadata is rechecked after payload preparation.

This tool binds accepted metadata; it does not repeat the large independent
payload rehash or reconciliation. The complete restoration payload remains in
the canonical backup location. Partial or stale receipts fail closed.

## Arguments, outputs and capacity

Required arguments:

- `--build-output`: exact successful builder directory listed above.
- `--boot-id`: current accepted CM5 boot UUID; observed
  `e60e67c2-f3f5-4b8b-8eab-2613df2de37e`. A later boot requires fresh admission.
- `--backup-complete-sha256` and `--backup-result-sha256`: the two actual
  root-accepted lowercase64-character hashes.
- `--backup-reviewer`: root's descriptive accepted reviewer,1–128 characters.

Output is always a fresh
`Q/audit-preparation/sidecar-stage30-v2-preparation-UUID` directory. It contains an
early CPU14 registered owner/scope, source triples, both preparer ancestry
copies, unchanged installer/action, exact build receipts, hash-bound backup
admission, independent decoded payload backup/restore, and `SOURCE_CLOSED.json`.
Failure is retained with `FAILURE.json`; output directories are never reused.
Root independently closes its exact PID/creation-FILETIME after natural return.

All archive and expanded package members are verified again through the exact
installer validator and full membership/readback. Existing bounds remain
8 MiB/600 seconds for preparation,2 MiB archive,16 MiB package, C:50 GiB/G:75 GiB
host free floors. Target reservation is
`expanded + archive + (directories + 1)*65536 + 65536`; the unchanged native
action additionally retains the physical5 GiB free reserve. These bound this
staging working set, not the user's recording corpus. Build30 retains build29
capacity policy and the8 MiB writable-admission floor above reserve.

## PowerShell

Only run after root accepts backup13 completion and grants the host slot.
The placeholders deliberately fail validation until replaced by actual pins.

```powershell
$stageDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/sqlite_sidecar_race_20261006'
$buildDir = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/sidecar-package30-99ab101518ce402a9a2c8d5f6ac96cc6'
$completePin = 'ROOT_ACCEPTED_BACKUP13_COMPLETE_SHA256'
$resultPin = 'ROOT_ACCEPTED_BACKUP13_RESULT_SHA256'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$stageDir/prepare_sidecar_stage30_v2.py" --build-output $buildDir --boot-id 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e' --backup-complete-sha256 $completePin --backup-result-sha256 $resultPin --backup-reviewer 'Codex root accepted completed backup13 restoration and exact closure'
```

Read the printed output and verify all source triples/decoded payload restores.
Preparation success is not native staging authority; root must review the
concrete prepared payload and dispatch it through the guarded native procedure.
Use a fresh native stage label. Existing failed/successful29 labels and roots
are retained and must not be replayed.

## CMD / Anaconda Prompt

Use the same existing Python directly; no environment installation or activation
is needed. Replace pins only after actual root acceptance and slot coordination.

```bat
set "JP_STAGE_DIR=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/sqlite_sidecar_race_20261006"
set "JP_BUILD_DIR=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/sidecar-package30-99ab101518ce402a9a2c8d5f6ac96cc6"
set "JP_COMPLETE_PIN=ROOT_ACCEPTED_BACKUP13_COMPLETE_SHA256"
set "JP_RESULT_PIN=ROOT_ACCEPTED_BACKUP13_RESULT_SHA256"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" "%JP_STAGE_DIR%/prepare_sidecar_stage30_v2.py" --build-output "%JP_BUILD_DIR%" --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e --backup-complete-sha256 "%JP_COMPLETE_PIN%" --backup-result-sha256 "%JP_RESULT_PIN%" --backup-reviewer "Codex root accepted completed backup13 restoration and exact closure"
```

## Current disposition

Prepared stage source only, not run. Backup13 COMPLETE/result acceptance remains
the prerequisite. Neither build success nor passing frozen29 native rows
qualifies changed30, activates it, changes Desktop, or authorizes journals to be
cleared. Record actual stage/native outcomes in a separate results note while
keeping reviewed source/payload hashes stable.

V2 prepares a fresh label after native Stage01's archive validation hit the
metadata utility's 128 MiB address-space limit before any installation. Use
a separately hash-bound finite 256 MiB staging utility, with current available
RAM checked and all source/filesystem/ownership guards retained. Stage01 raw
failure and exact utility closure remain preserved; it is not a successful stage.
