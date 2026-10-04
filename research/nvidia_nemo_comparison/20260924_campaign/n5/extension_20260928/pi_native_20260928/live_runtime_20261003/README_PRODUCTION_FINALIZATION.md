# Reviewed frozen-source production finalization

Purpose: prepare a fresh production package from an exact frozen qualification package after the root operator has reviewed the actual evidence. `finalize_production_release.py` performs host-only preparation. It does not contact the Pi, stage files, activate Desktop, start models or capture audio. No production acceptance is issued merely by preparing this source or its tests.

Release IDs are explicit inputs. Current production16 was built from disabled GUI15 with the same runtime content hash. The earlier production15 plan remains historical and unbuilt. The finalizer itself permits only same-content source-to-destination relocation. The separate, narrowly reviewed [GUI-only evidence helper](README_GUI_POLICY_REUSE.md) preserves actual14 measurements across the GUI policy-selection change before the unchanged native consumer validates the resulting authorization. Its certificate does not turn15/16 into measured model runs. The separately reviewed15-to16 path-only certificate remains mandatory.

The only builder extension is one AST insertion after BINDING is constructed and before the package inventory/archive: exact reviewed normal optional-refiner JSON documents are included under `authorization/optional-<sha256>.json`. These are authorization metadata excluded from the runtime content hash but included in PACKAGE_MANIFEST, the archive SHA and staging verification. Every reference must match its exact destination path, bytes/SHA, measured schema, selection, policy and destination binding/content/asset pins. Qualification permits and arbitrary extra files are refused. Missing optional proof leaves optional rows absent; it does not require postponing independently accepted ordinary rows.

Inputs are a SHA-pinned completed review, an exact frozen source manifest/binding/content, the existing reviewed external builder, an unaccepted destination plan, a reviewed path-only certificate, bounded pinned evidence and any independently approved optional normal admissions. Outputs are independent input copies, proof copies, accepted metadata, the new package/archive, BUILD_RESULT and FINALIZATION. Failed preparation is retained and never represented as an installed release.

Actual production16 is now staged, activated and consolidated to one shortcut; final Desktop Exec/policy-controls/normal Exit passed without Start, model or capture. The initial host readers failed after successful native activation/consolidation. Exact-scope [activation readback V2](README_ACTIVATION_READBACK_V2.md) and [consolidation readback V4](README_CONSOLIDATION_READBACK_V4.md) completed the respective10-file and46-member proofs without repeating native actions. Those original failures remain preserved. The final idle mirror includes37files/234564B with all nested owners and cgroups closed. This delivery result does not change the failed full-application hour or zero optional-correction result.

## Review input

Create the review only after reviewing the actual final outcomes. Until then keep `reviewed:false`; the tool refuses it. The exact top-level keys are:

| Key | Required value |
|---|---|
| schema | `just-peachy.production-finalization-review.v1` |
| reviewed, reviewer, reviewed_unix | Explicit completed review, nonempty reviewer, actual Unix time |
| source | `path`, `manifest_sha256`, `binding_sha256`, `content_sha256` of the frozen qualification package |
| destination_target | Exact fresh native `.../field-runtime-v29-build-NN` |
| builder | Local `path` and `sha256`; qualification14 inventory builder SHA `0a706522770d21d8b4846d3121cc430eef81ec73fcced965eca7d804fbf47832` |
| relocation_certificate | Local `path` and `sha256` of the existing reviewed same-content path-only certificate |
| production_plan | Local `path` and `sha256`; `accepted:false`, exact destination/content/installed pins, previous Desktop SHA, allowed selections, optional references, assets, finite limits and full_backup |
| proofs | 5–32 `{purpose,path,sha256}` entries; bounded local metadata, each at most2MiB |
| optional_documents | One `{native_path,path,sha256}` per exact optional reference; empty if no optional selections accepted |
| limitations | 1–32 explicit reviewed strings, maximum2048characters each |

Required proof purposes are `qualification`, `history_export`, `full_backup`, `selection_matrix`, `limitations`. Optional acceptance additionally requires `optional_live_measured`. These are review evidence pins, not an automatic quality/pass classifier. The root review must identify native functional evidence, unchanged selected code where relevant, actual source clocks/closure and unresolved sustained/quality limits. Do not turn the failed hour04 into a pass. GUI08/live300 and History13 actual proof may be retained through an explicit selected-code comparison; that does not imply the entire later candidate already ran.

The qualification14 builder's only code change from the earlier `8deb7b4f6ae26071597b00e27b85b401f3f9606205f026fcd451b85a46099876` builder is the explicit `admitted_identity.py` inventory member. Its immutable independent copy is `Q/audit-preparation/identity14-builder-source-006b6025a1db428094791fbcdf0dcf8c/prepare_package.py.after`. The finalizer permits these two exact builder hashes; use the new one for qualification14. No arbitrary module discovery or dynamic import bypass is added.

Use the actual backup03 receipt at `Q/production-backup-03-reconcile-01/FULL_BACKUP.json` and its verified manifest/completion. The builder rechecks all1932files/657980201B; it does not recopy them. Actual backup review: `Q/storage-preparation/backup03-verified-d4367ac9316d42b4b964f53342a9705f/REVIEW.json`. MANIFEST SHA `ac73aad726c84107c6814d80816dac8c5f7d1053070bf985f806407f8621a8b1`; COMPLETE SHA `cce6b7bf6b7168c567043bd0a57dfc3ad7d6f7d8338e6042eb59cc0cb93e9575`. This covers the selected current release/user-data scope, not every unchanged historical research root.

The standard246-row matrix is a configurable/validated selection matrix, not246 independent native measurements. Select only reviewed rows. Ordinary policy defaults remain300s source and120s drain/backlog. A600s accepted ceiling is only an upper bound for explicitly chosen developer policies, not a new ordinary default. Preserve the actual61-asset inventory and reviewed package-local component path mapping. Per-session native authorization still recomputes the exact selected inventory and checks every asset; the host finalizer cannot substitute a physical-machine measurement.

For a simple same-content optional relocation, the existing pure `optional_first_dispatch_20261003/release_review_tools.py` API remains applicable. Current production16 instead uses `gui_policy_reuse.compose_measured_admission` once directly from the original actual14 receipt, verifying both the GUI14-to15 and path15-to16 certificates. It preserves every measured/qualified/closure field and the exact live27-asset subset while changing only current content/operational pins plus explicit reuse provenance. Its packaged JSON is named `authorization/optional-<actual SHA>.json` and referenced by exact selection/policy/path/SHA. The saved26-asset subset is different and must not substitute for live27. Do not invent normal receipts from first-qualification, estimated RAM or preparation. No secondary selection is enabled without its own exact proof.

## PowerShell: host preparation

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
# Substitute the completed review and its independently checked SHA. Do not use a pending template.
& $py -B "$n/finalize_production_release.py" --review "$q/ACTUAL_REVIEW.json" --review-sha256 ACTUAL_SHA --execute-reviewed-build
if ($LASTEXITCODE -ne 0) { throw 'Preserve failed preparation; no stage or activation' }
```

The tool pins itself to CPU14, publishes actual PID/create_time/affinity before project reads, and allocates a unique `Q/storage-preparation/production-finalization-<uuid>` directory. It retains C:50GiB/G:75GiB plus128MiB independent preparation room. The exact source dependency imports are verified against the frozen manifest; no mutable runtime import is used. It verifies the full source tree before build and the full resulting tree afterward. Existing32MiB source/native metadata and2MiB compressed-package limits remain.

Command Prompt / Anaconda Prompt: enter `powershell -NoProfile`, then execute the complete block above using the qualified Python. No package/environment installation is needed.

## Root-only delivery order after successful finalization

1. Review FINALIZATION and BUILD_RESULT; stage only the exact resulting archive/manifest using the already reviewed staging action. Pin/read back the actual native package. Do not rebuild from mutable N or edit a frozen qualification release.
2. Fresh current baseline and production activation via `host_operations_v6.py --label desktop-activation-NN --action desktop_activation_action.py --payload ACTUAL_ACTIVATION.json --writes`. Payload requires current boot/expiry, package+manifest, acceptance and backup manifest/completion SHA, actual selected Desktop path/previous SHA, new activation evidence UUID and16777216 maximum output. See README_GUARDED_ACTIVATION.md. Actual activation01 already completed; its completed host proof is `readback_desktop_activation_v2.py --operation "$q/operation-desktop-activation-01" --output "$q/desktop-activation-01-readback-02"`, documented in [activation readback V2](README_ACTIVATION_READBACK_V2.md). These paths are existing evidence: do not rerun activation or reuse that occupied output. The reader is pinned to this exact completed operation, not a generic future activation reader.
3. The native consolidation action remains `host_operations_v6.py --label desktop-consolidation-NN --action desktop_consolidation_action_v3.py --payload ACTUAL_CONSOLIDATION.json --writes`, using the exact activation backup/current hash, retained11 shortcut/startup pins and fresh archive UUID. Actual consolidation01 already completed; its completed host proof is `readback_desktop_consolidation_v4.py --operation "$q/operation-desktop-consolidation-01" --output "$q/desktop-consolidation-01-readback-02"`, documented in [consolidation readback V4](README_CONSOLIDATION_READBACK_V4.md), with status COMPLETE_DESKTOP_ARCHIVE_READBACK. Do not repeat the native consolidation or reuse that occupied output. This reader also has exact completed-operation scope and cannot be reused generically. See README_DESKTOP_CONSOLIDATION_V3.md for the preserved transaction/restore procedure. No unrelated icons or startup changes are authorized.
4. Idle/normal Exit is last: dispatch `launch_production_idle_action_v2.py` with exact actual package/manifest/acceptance/current Desktop SHA, current boot/expiry, label `production-idle-NN`, `verify_optional_policy:true` and16777216 maximum output. It invokes the actual Desktop Exec/native_scope/default production data root, verifies actual remote Tk PID/ticks/cgroup, observes10stable480x800+0+0frames, exercises the exact optional60/30 policy and ordinary120/120 defaults through real controls with Start disabled, then invokes real Exit. Require complete closed mirror and separate nested GUI/scope/watchdog owner and cgroup closure. It starts no capture/models. Preserve disabled autostart/current settings/display270 and final Desktop membership evidence. See [idle V2](README_PRODUCTION_IDLE_V2.md).

Use the currently reviewed dispatcher if root has superseded V6; never bypass a historical-owner decoding refusal. No native actions are performed by this finalizer or its tests. No second full capture is implied by a targeted production idle/Exit check.

## Focused checks

`test_production_finalization.FinalizationBoundaryTests` checks only the new boundaries: exact one-statement builder AST insertion, actual manifest/archive inclusion through the unchanged serialization tail, pending/mismatched review refusal, and exact optional metadata membership/schema plus admission-validator dispatch. It uses synthetic metadata and does not claim actual optional or production acceptance. Run through the early-owner CPU14 wrapper in README_STORAGE.md; no models/native calls.
