# Build31 operator source adapter

Purpose: create one fresh private bundle of build31 stage, live/saved validation,
continuous-hour preparation/launch/review, and desktop activation helpers from
the exact frozen build30 sources. `prepare_caption31.py` is the only new tracked
operator implementation. It materializes reviewed substitutions and their full
receipt; it never executes the resulting helpers. Frozen29/30 sources and
packages remain unchanged.

Status: source prepared, not executed or tested. Actual build31 is sealed under
`Q/audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad`:
manifest `4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767`,
archive `e6d5e40c8c14ef5cc0e2e02d7d02894cdb48ac7a663cf34a334da36a0cd66db3`,
source review `6894adf19266061a15a71dc103d7317303652d68d58a4e27b74016430caaf4ca`,
independent closure `32b0dc450f080bda5f717f1082773222afaa14869c5223530fea421eec218919`.
All425 package/archive members were independently read back by the builder
closure audit; this adapter has not executed that verification itself yet.
There is no default build31
manifest, archive, source review, closure or proof hash. Actual reviewed build31
and independent closure must exist before this adapter can run. Build30 hour01
failed at 312 source seconds: its speaker lane reached the unchanged120-second
backlog gate. That prefix is not an hour pass. Build31's caption snapshot repair
requires its own native functional and sustained evidence.

## Inputs and outputs

Required inputs:

- The actual canonical `caption-package31-<32hex>` builder directory, its
  manifest/archive/source-review/independent-closure SHA256 pins, and reviewer.
  The authoritative builder receipts are `BUILD_RESULT.json`,
  `SOURCE_CLOSED.json`, `REGISTERED_OWNER.json`, `INDEPENDENT_CLOSURE.json`,
  `SOURCE_DIFF_REVIEW.json`, and `BUILD30_MEMBER_PRESERVATION.json`.
  The actual31 closure uses `natural_exit`, `exact_owner_absent`,
  `source_backups_and_independent_restores_exact`, `current_sources_unchanged`,
  `package_members`, and `archive_members_independently_restored`. The adapter
  reads those exact fields; it does not rewrite the original closure receipt.
- The actually observed native boot UUID. The adapter does not observe it.
- Root-accepted complete backup13 or14 reconciliation directory and its
  COMPLETE/RESULT/CENSUS SHA256 pins. Current31 preparation uses actual
  `production-backup-14-reconcile-01`, selected package30 and unit14 after
  reconciliation completes. The adapter retains small metadata admission;
  it does not recertify or copy the full backup payload. The derived stage
  preparer repeats the existing census/manifest/source/closure admission.
- An explicit root-selected live check number34–99. This binds the activation
  sources to one label. It does not assert that a future proof exists: activation
  preparation still requires the actual finalized PASS proof, full independently
  rehashed mirror, exact current owner/unit closure, and finalizer receipt.
- Exact frozen parent/dependency source files at their existing repair paths.
  Their eleven SHA256 pins are hardcoded in `PARENTS`; changed source rejects.
  Prior desktop30 RESULT is pinned to
  `0e2d1d0fa81e41fac84d8548ccf14904ff945905c4ede51613d2fccdb685973b`,
  desktop30 to
  `ef76ff090876de65491fa3aa845e2d4843228203c0e94c8ca921357d926d16d2`,
  and disabled autostart to
  `8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206`.

Output: fresh private `Q/audit-preparation/caption31-ops-<32hex>`, registered
CPU14 PID/creation FILETIME before project reads, actual input receipts,
source backups and independent restores, compiled derivative source copies,
`OPERATOR_BUNDLE.json` with every parent/substitution/output SHA, and
`SOURCE_CLOSED.json`. Syntax compilation does not run a helper or establish
native correctness. Root must independently check natural exit and exact PID
absence before another host compute slot is used.

The derived bundle contains:

- `prepare_core_stage31.py`: exact stage30V2 admission and installer delegation,
  binding actual31 target/archive/source review, parent30 preservation, and
  the selected complete backup. Original installer/action/reference SHA guards
  remain in place, and the emitted stage payload carries actual31 archive/PIN.
- `prepare_core_native_validation_v31.py`, plus byte-identical V2 native
  live/saved helpers: actual package inventory, ordinary row selection,
  12-second real UI capture, idle controls, Stop/drain, complete Discard,
  next chooser and independent finalization. The original finite helper scope
  and attribution/calibration conditions remain unchanged.
- `prepare_core_endurance31.py`, `launch_core_full_app_hour31.py`,
  `review_core_full_app_hour31.py`: original retained c24 lossless join and
  continuous hour route; one sample timeline, source/model session and all59
  wraps. No minute-by-minute model resets. The review remains numeric and
  read-only against a complete closed mirror.
- `launch_full_app_soak_action.py`: an exact byte-for-byte copy of the derived
  hour launcher under the basename admitted by the existing V8 dispatcher.
  Its SHA equals `launch_core_full_app_hour31.py`, with independent backup and
  restore. This preserves the separate3GiB hour reservation without raising
  the ordinary512MiB action ceiling.
- `stage_c24_endurance_input31.py`: optional fresh native input03 staging only.
  It must never be dispatched for existing input02. The actual accepted input02
  WAV can be reused by the hour preparation after original and staged hash
  verification. New input03 staging needs root's explicit choice and fresh
  preparation with its input03 path.
- `prepare_core_activation31.py`, `activate_core_desktop_action31.py`: exact
  finalized label proof and prior30 compare-and-swap. They retain the original
  inventory, full mirror, backup/independent restore and atomic shortcut
  transaction. Root must accept the fresh full backup14 before activation.
  Disabled login startup, recordings, galleries and calibration remain as
  recorded in the actual prior receipt.
- Exact `core_database_recovery.py` is included only for the existing pure
  file/JSON helpers imported by hour preparation. No database recovery action
  is run by this route.

## PowerShell: materialize the reviewed bundle

Use the existing interpreter and a coordinated host slot. No installation or
environment change is required. Replace every `ACTUAL_...` value with root's
accepted evidence. An unknown or fabricated PIN will fail before output
derivatives are created.

```powershell
$D='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$N=Split-Path $D
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$BUILD='ACTUAL_CLOSED_CAPTION_PACKAGE31_BUILDER_DIRECTORY'
$PIN='ACTUAL_ROOT_ACCEPTED_BUILD31_MANIFEST_SHA256'
$ARCHIVE_PIN='ACTUAL_ROOT_ACCEPTED_BUILD31_ARCHIVE_SHA256'
$SOURCE_REVIEW_PIN='ACTUAL_ROOT_REVIEWED_SOURCE_DIFF_SHA256'
$BUILD_CLOSURE_PIN='ACTUAL_INDEPENDENT_CLOSURE_SHA256'
$BOOT='ACTUAL_OBSERVED_CURRENT_NATIVE_BOOT'
$BACKUP='ACTUAL_ACCEPTED_BACKUP13_OR14_RECONCILIATION'
$BACKUP_COMPLETE_PIN='ACTUAL_ACCEPTED_COMPLETE_SHA256'
$BACKUP_RESULT_PIN='ACTUAL_ACCEPTED_BACKUP_RESULT_SHA256'
$BACKUP_CENSUS_PIN='ACTUAL_ACCEPTED_BACKUP_CENSUS_SHA256'
$REVIEWER='ACTUAL_ROOT_REVIEWER'
$LIVE_NUMBER=47 # Root-selected unused label; the proof remains pending.
& $PY -B "$D/caption_snapshot_20261006/ops31/prepare_caption31.py" --build-output $BUILD --manifest-sha256 $PIN --archive-sha256 $ARCHIVE_PIN --source-review-sha256 $SOURCE_REVIEW_PIN --build-closure-sha256 $BUILD_CLOSURE_PIN --boot-id $BOOT --backup-root $BACKUP --backup-complete-sha256 $BACKUP_COMPLETE_PIN --backup-result-sha256 $BACKUP_RESULT_PIN --backup-census-sha256 $BACKUP_CENSUS_PIN --reviewer $REVIEWER --live-check-number $LIVE_NUMBER
if($LASTEXITCODE -ne 0){throw 'Adapter failed; preserve its private receipt directory'}
```

Take `$OPS` from that actual returned `output`; do not guess its UUID. Record the
actual `bundle_sha256` and exact registered PID/FILETIME, independently prove
the process exited0 and is absent, and preserve source readback/closure. Before
using a bundle, rehash `OPERATOR_BUNDLE.json` against root's recorded SHA, and
rehash each used source, `.backup`, and `.restore` against its `files` entry.
The hour copy's SHA must equal the original derived launcher's entry. A source
change requires a fresh reviewed bundle, not editing a sealed copy.

## Stage and actual UI validation

Root alone dispatches native actions through the existing guarded V8 driver.
The following prep commands are host-only. Use actual fresh output labels;
neither a numbered label nor a preparation receipt is a native PASS.

```powershell
$OPS='ACTUAL_RETURNED_PRIVATE_OPS_DIRECTORY'
$PACK="$BUILD/package"
& $PY -B "$OPS/prepare_core_stage31.py" --build-output $BUILD --boot-id $BOOT --backup-complete-sha256 $BACKUP_COMPLETE_PIN --backup-result-sha256 $BACKUP_RESULT_PIN --backup-census-sha256 $BACKUP_CENSUS_PIN --backup-reviewer $REVIEWER
# Root checks the returned ACTION/PAYLOAD/source closure, then uses V8 --writes.
$LIVE_LABEL="classic-ui-check-$LIVE_NUMBER"
& $PY -B "$OPS/prepare_core_native_validation_v31.py" --package $PACK --manifest-sha256 $PIN --boot-id $BOOT --kind live --operator-id delayed_redimnet --label $LIVE_LABEL --discard-session
# Only after actual main/unit/nested-worker closure, prepare finalization:
& $PY -B "$OPS/prepare_core_native_validation_v31.py" --package $PACK --manifest-sha256 $PIN --boot-id $BOOT --kind live --operator-id delayed_redimnet --label $LIVE_LABEL --discard-session --operation finalize
```

The next saved check is root-selected Saved48 on `delayed_redimnet`, using
the same retained c24 speech. Existing six-row selection remains available;
no rerun of unchanged healthy rows is requested here. Operator IDs are `pyannote_redimnet`,
`pyannote_titanet`, `delayed_redimnet`, `delayed_titanet`,
`chunk52_2t_redimnet`, `chunk52_2t_titanet`. For the saved launch/finalize pair,
keep row, label, metadata, package and boot identical.

```powershell
$ROW='delayed_redimnet'
$SAVED_LABEL='classic-ui-check-48' # Root-selected unused31 saved label.
$C24_META='ACTUAL_ACCEPTED_BACKUP_PAYLOAD/runtime-data/recordings/sessions/c24b685b2bd34d6bb04172965d712c0f/session.json'
$C24_META_PIN='7da45b76193d3ddd1e2aa29bbc6792b019643c8a945edd3959d9458db4fc6c69'
& $PY -B "$OPS/prepare_core_native_validation_v31.py" --package $PACK --manifest-sha256 $PIN --boot-id $BOOT --kind saved --operator-id $ROW --label $SAVED_LABEL --saved-metadata-file $C24_META --saved-metadata-sha256 $C24_META_PIN --discard-session
& $PY -B "$OPS/prepare_core_native_validation_v31.py" --package $PACK --manifest-sha256 $PIN --boot-id $BOOT --kind saved --operator-id $ROW --label $SAVED_LABEL --saved-metadata-file $C24_META --saved-metadata-sha256 $C24_META_PIN --discard-session --operation finalize
```

Actual helper methods check SQLite normal-open recovery/quick_check, sidecars,
new capture and caption evidence, full Stop/drain and Discard, relaunch of the
chooser and independent closed owners. Eleven visible Mode controls are not
eleven acoustic/spatial quality tests. Do not substitute synthetic fixtures
for model/native quality or claim build30 rows qualify build31 automatically.

## Refresh hour preparation, job/full mirror, numeric review

Use accepted complete backup evidence holding the exact seven c24 processed
segment/source pins. Existing verified native input02 may be reused:

`/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/core-c24-endurance-input-02/c24-processed.wav`

WAV1,932,844bytes SHA256
`9a83534025736c2f057f20068f3c0584b45770815289a7842a501fcae52b65c8`;
PCM SHA256
`0f13e54972e4140f5797b996bdeb48d802acd4dcbb9407065d46190bda887e97`.
The native launch rechecks original source identities/hashes and the staged
join under the retained source shared lease. Input01 was never staged; do not
silently change to it. Input02 already exists, so skip native staging for it.

```powershell
$HOUR_LABEL='full-app-hour-02' # Root-selected unused31 hour after healthy47/48.
$C24_BACKUP='ACTUAL_ACCEPTED_COMPLETE_C24_BACKUP_ROOT'
$CENSUS_PIN='ACTUAL_C24_BACKUP_CENSUS_SHA256'
$COMPLETE_PIN='ACTUAL_C24_BACKUP_COMPLETE_SHA256'
$INPUT='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/core-c24-endurance-input-02/c24-processed.wav'
$PREP="$Q/audit-preparation/core-endurance31-refresh-$([guid]::NewGuid().ToString('N'))"
& $PY -B "$OPS/prepare_core_endurance31.py" --package $PACK --manifest-sha256 $PIN --backup-root $C24_BACKUP --census-sha256 $CENSUS_PIN --complete-sha256 $COMPLETE_PIN --boot-id $BOOT --native-input-path $INPUT --operator-id delayed_redimnet --label $HOUR_LABEL --reviewer $REVIEWER --output $PREP
if($LASTEXITCODE -ne 0){throw 'Fresh hour preparation failed'}
# Root only, after refreshed baseline/leases and exact host process closure:
$OP='core-hour31-launch-'+[guid]::NewGuid().ToString('N')
& $PY -B "$D/host_core_operations_v8.py" --label $OP --action "$OPS/launch_full_app_soak_action.py" --payload "$PREP/PAYLOAD.json" --writes
if($LASTEXITCODE -ne 0){throw 'Dispatch rejected or failed; preserve exact evidence'}
$dispatch=Get-Content -LiteralPath "$Q/operation-$OP/dispatch/RESULT.json" -Raw | ConvertFrom-Json
$job=$dispatch.action_result
if($job.schema -ne 'just-peachy.native-component-job.v1' -or $job.unit -ne "jp-v29-$HOUR_LABEL.service" -or $job.package_manifest_sha256 -ne $PIN -or $job.workflow -ne 'continuous-full-application-repeated-wav'){throw 'Actual returned job differs'}
$JOB="$Q/$HOUR_LABEL-JOB.json"
$bytes=[Text.Encoding]::UTF8.GetBytes(($job | ConvertTo-Json -Depth 50 -Compress))
$stream=[IO.File]::Open($JOB,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
$MIRROR="$Q/$HOUR_LABEL-monitor-$([guid]::NewGuid().ToString('N'))"
& $PY -B "$N/monitor_native_job.py" --job $JOB --output $MIRROR --poll-seconds 15 --copy-deadline-seconds 7200
if($LASTEXITCODE -ne 0){throw 'Complete mirror not accepted; retain partial evidence'}
# Only after actual FULL_CLOSED_OUTPUT_MIRRORED and MIRROR_COMPLETE:
& $PY -B "$OPS/review_core_full_app_hour31.py" --mirror $MIRROR --package $PACK --manifest-sha256 $PIN --output-root "$Q/audit-preparation"
```

The retained600-second admission is a start window. The dispatch helper exits
after service launch; it does not restrict the service to600seconds. The source
policy allows3600source +120loading +600drain +60cleanup =4380seconds. The unit
adds300seconds, preserving RuntimeMaxSec4680, wrapper alarm4670, and original
JOB deadline registration slack. A7200-second mirror allowance extends only
closure/copy, not native compute. Refresh to a new `$PREP` after expiry; never
edit an old payload's time or extend the backlog/uncertainty gate.

Native and independent PC reservations retain the full complete-output plan
(historically2,306,682,336bytes each), ceiling3GiB/2048files. The existing V8
metadata helper scope remains CPU3/AS256MiB/stack1MiB/FSIZE32MiB/600seconds;
the model session retains its own original memory/CPU limits. Per-file FSIZE
is derived from actual filesystem total minus the physical StoragePolicy
reserve, at least5GiB, with free-space admission. Host floors C:50GiB/G:75GiB
and twice the complete output plus8MiB remain. No global limit is raised.

Review requires57,600,000samples,59 exact wraps, one model/source session,
honest final3600-second clocks, caption/PnC/source completion, zero final lag
and drops, bounded queues, SQLite integrity, natural worker/job closure and
physical capacity evidence. Failure remains `FAILED_OR_INCOMPLETE_PREFIX`.
Repeated retained speech is not natural conversation, microphone/spatial
behavior, GUI endurance or acoustic-quality qualification.

## Activation after actual finalized proof and fresh backup14

Root first accepts the complete fresh backup14 and rechecks baseline/leases.
The number sealed into `$OPS` must match the actual finalized31 live proof.
If root selected a different label, create a new reviewed bundle. The host
preparer refuses partial mirrors or invented future proof.

```powershell
& $PY -B "$OPS/prepare_core_activation31.py" --native-check-file 'ACTUAL_FINALIZED_LIVE31_MIRROR/closed-output/NATIVE_CHECK_V2.json' --finalizer-result 'ACTUAL_LIVE31_FINALIZER_RESULT_JSON' --boot-id $BOOT --manifest-sha256 $PIN --mirror-complete-sha256 ACTUAL_ACCEPTED_MIRROR_COMPLETE_SHA256 --finalizer-result-sha256 ACTUAL_ACCEPTED_FINALIZER_SHA256
# Root dispatches only the actual returned backed ACTION/PAYLOAD via V8 --writes.
```

## CMD and Anaconda Prompt

Use the same existing interpreter explicitly; an Anaconda Prompt need not
activate or install another environment. Set actual values, then run the same
arguments as PowerShell. `%OPS%` is the actual emitted bundle directory.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "ADAPTER=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\caption_snapshot_20261006\ops31\prepare_caption31.py"
"%PY%" -B "%ADAPTER%" --build-output ACTUAL_BUILD31_DIRECTORY --manifest-sha256 ACTUAL_BUILD31_MANIFEST_SHA --archive-sha256 ACTUAL_ARCHIVE_SHA --source-review-sha256 ACTUAL_SOURCE_REVIEW_SHA --build-closure-sha256 ACTUAL_INDEPENDENT_CLOSURE_SHA --boot-id ACTUAL_CURRENT_BOOT --backup-root ACTUAL_COMPLETE_BACKUP14 --backup-complete-sha256 ACTUAL_COMPLETE_SHA --backup-result-sha256 ACTUAL_BACKUP_RESULT_SHA --backup-census-sha256 ACTUAL_CENSUS_SHA --reviewer ACTUAL_REVIEWER --live-check-number 47
set "OPS=ACTUAL_RETURNED_PRIVATE_OPS_DIRECTORY"
set "PACK=ACTUAL_BUILD31_DIRECTORY\package"
set "PIN=ACTUAL_BUILD31_MANIFEST_SHA"
set "BOOT=ACTUAL_CURRENT_BOOT"
"%PY%" -B "%OPS%\prepare_core_native_validation_v31.py" --package "%PACK%" --manifest-sha256 %PIN% --boot-id %BOOT% --kind live --operator-id delayed_redimnet --label classic-ui-check-47 --discard-session
"%PY%" -B "%OPS%\prepare_core_native_validation_v31.py" --package "%PACK%" --manifest-sha256 %PIN% --boot-id %BOOT% --kind live --operator-id delayed_redimnet --label classic-ui-check-47 --discard-session --operation finalize
"%PY%" -B "%OPS%\review_core_full_app_hour31.py" --mirror ACTUAL_FULL_CLOSED_MIRROR --package "%PACK%" --manifest-sha256 %PIN% --output-root ACTUAL_PRIVATE_AUDIT_PARENT
```

All remaining commands retain identical script arguments: replace the
PowerShell `& $PY` prefix with `"%PY%"` and variables with actual quoted paths.
Native helpers use injected PAYLOAD/BASELINE and RESULT, not a stdin CLI. Root
alone controls native admission and sequential dispatch. Update this README
with actual package/bundle pins, process closure and evidence when available;
do not replace pending scope with fixture quality claims.
