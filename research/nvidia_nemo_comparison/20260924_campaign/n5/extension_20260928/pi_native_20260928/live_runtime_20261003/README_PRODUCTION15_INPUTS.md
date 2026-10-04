# Production15 inputs and final delivery order — unaccepted recipe

**Historical, unbuilt plan:** This document preserves the earlier proposed14-to15 production recipe. It was superseded by GUI-only candidate15 and production16. Use [current production16 inputs](README_PRODUCTION16_INPUTS.md) and [the reviewed finalizer](README_PRODUCTION_FINALIZATION.md); do not run these old target15 commands for the delivered release. Actual Followup02 later passed its exact live300 scope with zero optional corrections. Followup01 failed an active30-second label-lag limit, not an EOF allowance.


Purpose: collect the actual qualification14 evidence and exact native payloads needed for a same-content production15 release. This is a template, not acceptance, an admission or a dispatch request. No production15 build, native action or final handoff ZIP is performed by writing this document.

Inputs: the actual admitted14 source package, reviewed final14 outcomes, existing verified backup03, actual asset/selection inventory, path-only relocation review and final Desktop state. Outputs: a completed review for `finalize_production_release.py`, then fresh root-operated stage/activation/consolidation/idle payloads and their independent readbacks. Keep every earlier failed and disabled receipt unchanged.

## Fill only from actual final evidence

The disabled14 content is `efba7bf123f2e46769bb20655d2998f83a8ed6da48760438ef84fc0582efb0cd`, at `Q/audit-preparation/identity-derivative-0e148ab38dfe45faa37d15d802e71cdd/package`. Its disabled manifest is `6e0ccf2eb0348ae4b73865daa4dd011d5a1b3c1ec87883d156c28da36ce1326d`. These are source-preparation facts only. **Do not use its binding/manifest as the later admitted14 source.** Fill the review with the actually admitted/staged14 manifest and BINDING SHA after that operation completes.

Actual admitted14 was subsequently staged: local package `Q/audit-preparation/package-preparation-44b6fb3f972446219644fd4f53e008b6/package`, manifest `8ec7f83c148d4cf5b043f0a8f044033b6881164b83f0c7bdb3d5af7757e0dcb8`, raw BINDING SHA `6b768ec1482cef7c72efd7542eb239104eb0acdb335fefc6690834676f1ab633`, same content above. This supplies source pins; qualification outcomes remain pending.

Actual primary-alone08 saved45, optional First03 and repaired Research07 now have closed reviewed evidence. The optional selection explicitly sets `revision_window_seconds=60`; First03's finite saved45 policy separately sets `max_drain_seconds=60`. Live Followup02 and its exact policy require their own closed review; a revision-window value is not a general EOF guarantee. Preserve short First02 feasibility, failed live Followup01 secondary30-second EOF timeout, research06 projection failure and full-application hour04 failure as separate provenance. Do not change all-runtime content pins to reuse older optional evidence. Production15 only relocates the exact qualified14 runtime content.

The review must decide allowed rows and limitations. The246 default rows are a validated selection matrix, not246 native experiments. Ordinary normal source/drain/backlog remain300/120/120seconds. Larger accepted ceilings do not silently alter those defaults. Add an optional row only with its exact measured normal admission for that source/embedding/complete policy. Otherwise leave optional references/documents empty.

Production acceptance is intended to authorize field testing of reviewed configured live/saved rows with their experimental flags and resource guards. It must not claim246 measured, sustained or quality passes. The failed full-application hour04 and successful isolated Chunk52 component hour remain separate.

Use backup03's actual full selected-release/user-data proof:1932files,657980201bytes, natural guard closure and independent source/PC readback. Its MANIFEST SHA is `ac73aad726c84107c6814d80816dac8c5f7d1053070bf985f806407f8621a8b1`; COMPLETE SHA is `cce6b7bf6b7168c567043bd0a57dfc3ad7d6f7d8338e6042eb59cc0cb93e9575`. Retained historical research exclusions remain explicit. Preserve all61 actual asset pins and map only the reviewed identical package-local component-evidence path to15.

`prepare_production15_plan.py` creates the unaccepted plan, disabled destination binding preview, unreviewed relocation certificate, pending proof slots and independently copied frozen builder/dependencies. It verifies the admitted14 full inventory, exact246-row/profile source and61-asset inputs, and existing backup03 metadata. It does not build a package or claim fresh native asset measurement. Purpose, inputs and outputs are those files; use the command below after setting `$py`, `$n` and `$q` as in the final section:

```powershell
$old="$q/audit-preparation/production13-plan-fda43f06a54c42df9d75b9f8c556a446"
& $py -B "$n/prepare_production15_plan.py" --source "$q/audit-preparation/package-preparation-44b6fb3f972446219644fd4f53e008b6/package" --source-manifest-sha256 8ec7f83c148d4cf5b043f0a8f044033b6881164b83f0c7bdb3d5af7757e0dcb8 --matrix "$old/SUPPORTED_DEFAULT_SELECTIONS_REQUIRES_REVIEW.json" --assets "$old/SELECTED_ASSETS_ACTUAL_SOURCE.json" --builder "$q/audit-preparation/identity14-builder-source-006b6025a1db428094791fbcdf0dcf8c/prepare_package.py.after" --full-backup "$q/production-backup-03-reconcile-01/FULL_BACKUP.json" --output-root "$q/audit-preparation"
```

## Final review template

Write this privately and replace every `ACTUAL_...` value. It deliberately refuses execution while `reviewed` is false or hashes are placeholders. `production_plan` points to the complete unaccepted plan with exact allowed selections, optional references, assets, limits and full_backup. Construct the path-only certificate from actual admitted14 to15 using the existing relocation contract; separately review it. The finalizer verifies both.

```json
{
  "schema": "just-peachy.production-finalization-review.v1",
  "reviewed": false,
  "reviewer": "ACTUAL_FINAL_REVIEWER",
  "reviewed_unix": 0,
  "source": {
    "path": "ACTUAL_LOCAL_ADMITTED14_PACKAGE",
    "manifest_sha256": "ACTUAL_ADMITTED14_MANIFEST_SHA",
    "binding_sha256": "ACTUAL_ADMITTED14_BINDING_SHA",
    "content_sha256": "efba7bf123f2e46769bb20655d2998f83a8ed6da48760438ef84fc0582efb0cd"
  },
  "destination_target": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-15",
  "builder": {
    "path": "ACTUAL_LOCAL_PINNED_BUILDER_COPY",
    "sha256": "0a706522770d21d8b4846d3121cc430eef81ec73fcced965eca7d804fbf47832"
  },
  "relocation_certificate": {"path": "ACTUAL_REVIEWED_14_TO_15_CERTIFICATE", "sha256": "ACTUAL_SHA"},
  "production_plan": {"path": "ACTUAL_UNACCEPTED15_PLAN", "sha256": "ACTUAL_SHA"},
  "proofs": [
    {"purpose": "qualification", "path": "ACTUAL_FINAL14_REVIEW", "sha256": "ACTUAL_SHA"},
    {"purpose": "history_export", "path": "ACTUAL_HISTORY04_REVIEW", "sha256": "ACTUAL_SHA"},
    {"purpose": "full_backup", "path": "ACTUAL_BACKUP03_REVIEW", "sha256": "ACTUAL_SHA"},
    {"purpose": "selection_matrix", "path": "ACTUAL_ALLOWED_SELECTION_REVIEW", "sha256": "ACTUAL_SHA"},
    {"purpose": "limitations", "path": "ACTUAL_REVIEWED_LIMITATIONS", "sha256": "ACTUAL_SHA"}
  ],
  "optional_documents": [],
  "limitations": ["ACTUAL_REVIEWED_LIMITATIONS; no whole-application hour or general speech-quality pass inferred"]
}
```

If accepting an optional row, add `optional_live_measured` to proofs and use the existing reviewed path-only `reuse_measured_admission` helper. Put its exact returned JSON at `authorization/optional-<itsSHA>.json` in destination15 via the finalizer, with the exact reference selection/policy/asset inventory. Add `{native_path,path,sha256}` to optional_documents for each receipt. This is post-content metadata included in the manifest/archive. The helper and the finalizer do not produce a measured receipt from estimates. See [finalizer contract](README_PRODUCTION_FINALIZATION.md).

## Native payload templates after actual production preparation/stage

All payloads use a current exact boot and a new expiry no more than600seconds ahead. The zeros and strings below are deliberately unlaunchable. A new baseline must show exact old owner closure and free leases. Activation and consolidation create no process/capture. Their inspector metadata reservation remains16777216bytes and file ceiling33554432bytes.

Activation input:

```json
{
  "boot_id": "ACTUAL_CURRENT_BOOT", "expires_unix": 0,
  "package": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-15",
  "package_manifest_sha256": "ACTUAL_STAGED15_MANIFEST_SHA",
  "production_acceptance_sha256": "ACTUAL15_ACCEPTANCE_SHA",
  "backup_manifest_sha256": "ac73aad726c84107c6814d80816dac8c5f7d1053070bf985f806407f8621a8b1",
  "backup_completion_sha256": "cce6b7bf6b7168c567043bd0a57dfc3ad7d6f7d8338e6042eb59cc0cb93e9575",
  "desktop": "/home/peachyprototype/Desktop/ACTUAL_SELECTED_OWNED_BASENAME.desktop",
  "previous_desktop_sha256": "ACTUAL_ACCEPTED_OLD_DESKTOP_SHA",
  "evidence_root": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-activation-ACTUAL32HEXUUID",
  "maximum_output_bytes": 16777216
}
```

After activation's complete PC readback, construct consolidation using its returned `backup` and `current_sha256`, not guessed paths/hashes:

```json
{
  "mode": "consolidate", "boot_id": "ACTUAL_CURRENT_BOOT", "expires_unix": 0,
  "package": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-15",
  "package_manifest_sha256": "ACTUAL_STAGED15_MANIFEST_SHA",
  "selected": "ACTUAL_SELECTED_OWNED_BASENAME.desktop",
  "activation_backup": "ACTUAL_ACTIVATION_RETURNED_BACKUP_PATH",
  "expected_current_sha256": "ACTUAL_ACTIVATION_RETURNED_CURRENT_SHA",
  "archive": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-desktop-consolidation-ACTUAL32HEXUUID",
  "maximum_output_bytes": 16777216
}
```

The selected basename must be one of V3's exact11 retained entries and match the actual activation plan. V3 verifies all11 originals plus both startup files against the complete backup. It archives the other10 outside Desktop and returns all46archive files; unrelated icons stay untouched. Explicit restore uses mode `restore`, the same preserved archive and fresh boot/expiry/label; no automatic retry/rollback.

After V3 complete archive readback, prepare idle-last:

```json
{
  "label": "production-idle-01", "boot_id": "ACTUAL_CURRENT_BOOT", "expires_unix": 0,
  "package": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-15",
  "package_manifest_sha256": "ACTUAL_STAGED15_MANIFEST_SHA",
  "production_acceptance_sha256": "ACTUAL15_ACCEPTANCE_SHA",
  "desktop": "/home/peachyprototype/Desktop/ACTUAL_SELECTED_OWNED_BASENAME.desktop",
  "desktop_sha256": "ACTUAL_UNIFIED_CURRENT_DESKTOP_SHA",
  "maximum_output_bytes": 16777216
}
```

The idle action requires the exact default `~/JustPeachy/data/runtime-v29` absent or empty; it does not silently substitute a test data root. It verifies the exact activated Desktop Exec, runs its actual native_scope, proves the Tk interpreter PID/ticks/cgroup, collects10stable fullscreen480x800+0+0 observations and invokes real Exit. The production service retains its7200second property; an independent90second watchdog bounds the test. Require nested GUI/scope/watchdog closure in addition to the outer job's closed mirror, unchanged display270/startup/settings and final Desktop hash/membership. No Start, capture or model construction is part of this check.

## PowerShell / Command Prompt / Anaconda sequence

In Command Prompt or Anaconda Prompt, first enter `powershell -NoProfile`. Use the qualified interpreter; no environment install is required. Root alone executes native commands. Substitute final input names and fresh two-digit labels:

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
& $py -B "$n/finalize_production_release.py" --review "$q/ACTUAL_REVIEW15.json" --review-sha256 ACTUAL_REVIEW_SHA --execute-reviewed-build
# Stop on failure. Stage/read back only its actual final archive and manifest using the reviewed stage action.
& $py -B "$n/host_operations_v6.py" --label desktop-activation-01 --action "$n/desktop_activation_action.py" --payload "$q/ACTUAL_ACTIVATION15.json" --writes
& $py -B "$n/desktop_activation_action.py" --operation "$q/operation-desktop-activation-01" --output "$q/desktop-activation-01-readback-01"
# Require the above complete natural-closure readback before constructing the next payload.
& $py -B "$n/host_operations_v6.py" --label desktop-consolidation-01 --action "$n/desktop_consolidation_action_v3.py" --payload "$q/ACTUAL_CONSOLIDATION15.json" --writes
& $py -B "$n/desktop_consolidation_action_v3.py" --operation "$q/operation-desktop-consolidation-01" --output "$q/desktop-consolidation-01-readback-01"
# Require COMPLETE_DESKTOP_ARCHIVE_READBACK, then idle is the final native action.
& $py -B "$n/host_operations_v6.py" --label production-idle-launch-01 --action "$n/launch_production_idle_action.py" --payload "$q/ACTUAL_IDLE15.json" --writes
# Persist the exact returned JOB before using the existing reviewed monitor; review nested closure and all resulting evidence.
```

Run each step separately, inspect its exit code and receipts, and stop on failure. The comments are gates, not authorization to paste an uninterrupted batch. Use a newer reviewed dispatcher only when root has explicitly selected its exact backed bytes. See [guarded activation](README_GUARDED_ACTIVATION.md), [complete consolidation readback](README_DESKTOP_CONSOLIDATION_V3.md) and [public-source handoff](README_FINAL_PUBLICATION.md). Final publication follows the actual idle closure review and fresh public whitelist hashing; this recipe creates no final archive.
