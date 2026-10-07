# Build32 operator source preparation

Purpose: materialize a fresh private build32 operator bundle from the exact
reviewed build31 generator template and its eleven frozen build30 source/helper
parents. Only this generator and maintained README are new tracked files; the
stage, validation, hour and activation actions are generated in private host
evidence. No duplicate collection of native actions is added to the source tree.

Status: source only. No build32 package/pins, operator preparation, native stage,
validation, hour run or activation is claimed here. Sealed31 remains immutable;
the actual prior desktop remains activated30. The separate build32 builder must
first produce a reviewed package and independently closed archive evidence.
This program performs host source preparation only; it does not execute SSH,
import runtime/model code, open SQLite, edit data or change the desktop.

Inputs are the actual canonical `gallery-package32-UUID` build output and exact
root-accepted manifest, archive, content, source-review and independent-closure
SHA256 values. The build must derive from sealed31 manifest
`4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767`.
The preparer independently rehashes complete package membership and the archive,
checks builder/closure/member-preservation evidence, and binds the new gallery
source-review schema. It does not invent future package hashes.

The required accepted backup is `production-backup-14-reconcile-01`, whose
COMPLETE/RESULT/CENSUS hashes are respectively:

- `9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e`
- `1154c795a07e35941d21f99fc81617f0534dd3de51771c070d031ce526d2f879`
- `509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263`

Metadata admission preserves its COMPLETE selected-release/user-data scope,
boot/package owner, source-before/after and external-asset checks, full census
and manifest equality. Full private backup payload readback is the accepted
root evidence; this source preparer rechecks and backs up metadata, and the
generated stage preparer repeats the full admission guard. The current boot is
fixed to `e60e67c2-f3f5-4b8b-8eab-2613df2de37e`. A reboot or different accepted
backup needs a separately reviewed source version.

The source template is `caption_snapshot_20261006/ops31/prepare_caption31.py`,
SHA256 `f0ffe35c4360447b0039e063e79e72bd8ac274ff5ce2e2e7afb219230e240cef`.
All eleven original parent/helper SHAs remain exact. The build32 bundle changes
version/pin/control-source bindings, stage preservation filename and fresh
labels; CPU, AS, RAM/disk floors, timers, actual allocations, source math, models,
namespaces and native helper code remain the original reviewed contracts.

Outputs are a fresh `Q/audit-preparation/gallery32-ops-UUID` directory with early
CPU14/PID/creation-FILETIME registration, CreateNew source/metadata backups and
independent restores, generated helper triples, `OPERATOR_BUNDLE.json` and
`SOURCE_CLOSED.json`. `Q` is
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003`.
Every output is read back, and all input bytes are rechecked at closure. The
existing 8 MiB/600-second host preparation scope and actual C:/G:/ free floors
remain. Natural process return and exact OS owner absence require the independent
host closure step before any other host Python or native action starts.

## Prepare after the actual build is accepted

Coordinate one CPU14 host slot. Use the configured interpreter; no conda install
or model download is required. All placeholders below must come from actual
sealed build32 receipts. These commands are instructions for a later accepted
phase, not authorization or evidence that it has run.

PowerShell:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B "$d/capacity_gallery_20261006/ops32/prepare_gallery32.py" `
  --build-output 'ACTUAL_GALLERY_PACKAGE32_OUTPUT' `
  --manifest-sha256 ACTUAL_PIN32 --archive-sha256 ACTUAL_ARCHIVE32_SHA `
  --content-sha256 ACTUAL_CONTENT32_SHA --source-review-sha256 ACTUAL_REVIEW32_SHA `
  --build-closure-sha256 ACTUAL_INDEPENDENT_CLOSURE32_SHA `
  --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e `
  --backup-root "$q/production-backup-14-reconcile-01" `
  --backup-complete-sha256 9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e `
  --backup-result-sha256 1154c795a07e35941d21f99fc81617f0534dd3de51771c070d031ce526d2f879 `
  --backup-census-sha256 509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263 `
  --live-check-number 49 --saved-check-number 50 --reviewer 'ACTUAL_ROOT_REVIEWER'
```

Command Prompt and Anaconda Prompt:

```bat
set "JP_OPS=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\capacity_gallery_20261006\ops32"
set "JP_Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%JP_OPS%\prepare_gallery32.py" --build-output "ACTUAL_GALLERY_PACKAGE32_OUTPUT" --manifest-sha256 ACTUAL_PIN32 --archive-sha256 ACTUAL_ARCHIVE32_SHA --content-sha256 ACTUAL_CONTENT32_SHA --source-review-sha256 ACTUAL_REVIEW32_SHA --build-closure-sha256 ACTUAL_INDEPENDENT_CLOSURE32_SHA --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e --backup-root "%JP_Q%\production-backup-14-reconcile-01" --backup-complete-sha256 9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e --backup-result-sha256 1154c795a07e35941d21f99fc81617f0534dd3de51771c070d031ce526d2f879 --backup-census-sha256 509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263 --live-check-number 49 --saved-check-number 50 --reviewer "ACTUAL_ROOT_REVIEWER"
```

## Generated operations and boundaries

Read `OPERATOR_BUNDLE.json` and its exact file pins, then independently close the
preparation owner. `prepare_core_stage32.py` consumes the actual package builder
root, current boot and the same accepted backup pins. The fixed fresh stage
label is `core-stage32-01`. Do not dispatch while the owned hour31 process or
any other native lease is active. The old dispatcher V9 admits only exact31's
exception; a stage32 payload above 2 MiB requires a new separately reviewed V10
exception bound to actual measured32 archive/action/payload hashes. No blanket
host or native limit increase is made here.

For focused validation, the generated
`prepare_core_native_validation_v32.py` retains the original exact helper pins,
full allocations, ordinary package origins, source and owner guards. Use fresh
Live49 with `--kind live --operator-id delayed_titanet --label classic-ui-check-49
--discard-session`. Use Saved50 with `--kind saved --operator-id delayed_redimnet
--label classic-ui-check-50 --saved-metadata-file ACTUAL_VERIFIED_C24_METADATA
--saved-metadata-sha256 ACTUAL_METADATA_SHA`. Supply its actual package/PIN32 and
current boot arguments. Launch, exact closure, full independent native/PC mirror
and separate finalize remain distinct required phases. Old results do not
qualify new code. Do not create an activation payload from source-only/prepared
or merely functional results.

The hour helpers preserve 3600 seconds of the same repeated accepted C24 speech,
4680-second unit runtime, 120-second analyzed-source backlog gate and the original
complete native/PC allocation (2,306,682,336 bytes and 2048 files per side, within
the guarded 3 GiB allowance). The <=600-second preparation/start-admission window
is distinct from the longer owned unit lifetime. `launch_full_app_soak_action.py`
is the exact-byte admitted basename copy of the generated hour action. Source
input reuse or a new fixed C24 stage must retain actual existing source proofs;
no new corpus, model or source math is introduced.

The activation preparer/action require future actual Live49 finalized PASS,
independent complete mirror/closure, correct build32 content and current boot.
They retain prior desktop30 compare-and-swap SHA256
`ef76ff090876de65491fa3aa845e2d4843228203c0e94c8ca921357d926d16d2`,
actual prior activation RESULT SHA256
`0e2d1d0fa81e41fac84d8548ccf14904ff945905c4ede51613d2fccdb685973b`,
and exact disabled autostart bytes. Current desktop30 and rollback releases are
preserved until an explicit accepted activation. Root requires a fresh accepted
backup before activation; backup14's staging prerequisite alone does not claim
coverage of later retained data. Activation itself starts no capture or model.

Update this maintained README with actual prepared source pins, owner closure,
stage dispatch/version and finalized outcomes when those phases occur. A host
prepared bundle or fixture PASS does not prove native gallery behavior, speech
quality or hour-long realtime sustainability.
