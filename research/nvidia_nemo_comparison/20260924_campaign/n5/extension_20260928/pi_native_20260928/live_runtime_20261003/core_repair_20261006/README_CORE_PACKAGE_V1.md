# Review and build the immutable build29 candidate

Purpose: create a host-only source review and, after root review, a separate
immutable `field-runtime-v29-build-29` package from the exact complete build28
inventory. `build_core_package_v1.py` never contacts the Pi, opens production
data, loads models, changes the desktop or activates a release. Build28 remains
unchanged. Native staging is forbidden while the production backup holds leases.

Inputs are the exact private build28 package at
`audit-preparation/stabilization-package-0c72a531741047998278d56d381effc2/package`,
manifest SHA256 `e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b`,
the explicit candidate runtime/helper/README replacement tuple in the builder,
and the unchanged `ui_restore_20261004/build_classic_package.py` core pinned to
SHA256 `bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5`.
Build additionally requires the exact `SOURCE_DIFF_REVIEW.json`, its SHA256 and
an explicit reviewer label after root has reviewed its concrete source inventory.

Outputs use a fresh private `audit-preparation/core-package-v1-<uuid>` directory:
early exact Windows owner (CPU14, PID, creation FILETIME), finite host scope,
all input backups and separate restored copies, complete source pins,
function/method/closure AST changes with old/new hashes and source lines,
module-scope AST hashes and static local import reachability. Review-only stops
there. Build emits the preserved-member receipt, separate package/manifest,
readback-verified tar.gz archive, pure acceptance-validator results,
`BUILD_RESULT.json` and `SOURCE_CLOSED.json`. Previous output roots are never
reused or overwritten; failures remain evidence.

The builder reuses the SHA-pinned core inventory, derive, output, acceptance
validation, archive construction and complete archive-member restore checks.
Only the core main function's single archive basename literal changes to
`field-runtime-v29-build-29-prepared.tar.gz`. The bounded core is imported only
after early owner registration; runtime modules are parsed/compiled, never
executed. The inherited 600-second/16 MiB preparation, 16 MiB expanded package,
2 MiB member/archive, 512-member and C:50/G:75 GiB floors remain verification
budgets. Supervision must independently confirm the exact owner is absent after
exit, and enforce exact-owner closure if a broken check hangs.

## Scope that the root review must assess

The explicit replacements cover storage/startup/file admission, writer capacity,
caption rendering/history, native recognition-segment/group handling and
identity/mode/gallery-snapshot integration. Their paired maintained READMEs
document purposes, inputs/outputs and isolated commands.
`README_GALLERY_CAPACITY.md` accompanies `gallery_snapshot_io.py` explicitly.
Test runners and native
inspection/backup tools are excluded from the runtime archive and belong in
the final source handoff instead. All runtime helper imports must be statically
reachable from launcher/worker/native_scope through packaged local modules.
External/model imports are preserved and not executed by this check.

All other parent package members remain byte-identical: model/backend/profile
descriptors, physical raw source, raw qualification documents, calibrations,
galleries, source assets, operational data-root location and physical policy
fields. The raw-proof binding changes only its exact build28 prefix to build29;
proof/source bytes and historical qualification scope remain unchanged.

Provenance explicitly records `resource_storage_policy_changed:true` because
logical metadata/text-writer quotas and the fixed global SQLite file ceiling
were removed under the user's instruction. Actual physical free-space reserves,
memory/queue bounds, ownership and bounded transaction guards remain. The
inherited inaccurate `resource_storage_policy_changed:false` is not retained.
Acceptance limitations are rewritten for this candidate, preserving the ordinary
246 guarded selections and disabling reuse of old optional-refiner admissions.
No historical native measurement becomes a build29 or quality pass.

## Run commands

Wait until root releases a host slot; caption/identity checks and the backup
share the guarded host process budget. Review first; these commands do not
authorize staging or activation.

PowerShell:

```powershell
$py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$repair = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
& $py -B "$repair/build_core_package_v1.py" --review-only
# Read SOURCE_DIFF_REVIEW.json from the fresh output, then root reviews it.
$review = 'PASTE-FRESH-REVIEW-OUTPUT/SOURCE_DIFF_REVIEW.json'
$reviewSha = (Get-FileHash -LiteralPath $review -Algorithm SHA256).Hash.ToLowerInvariant()
& $py -B "$repair/build_core_package_v1.py" --review-manifest $review --review-sha256 $reviewSha --reviewer 'Codex root reviewed the exact build29 source inventory'
```

Command Prompt:

```cmd
set "PY=C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe"
set "REPAIR=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006"
"%PY%" -B "%REPAIR%/build_core_package_v1.py" --review-only
rem Read the emitted fresh SOURCE_DIFF_REVIEW.json and have root review it.
set "REVIEW=PASTE-FRESH-REVIEW-OUTPUT/SOURCE_DIFF_REVIEW.json"
certutil -hashfile "%REVIEW%" SHA256
set "REVIEW_SHA=PASTE-EXACT-PRINTED-SHA256"
"%PY%" -B "%REPAIR%/build_core_package_v1.py" --review-manifest "%REVIEW%" --review-sha256 "%REVIEW_SHA%" --reviewer "Codex root reviewed the exact build29 source inventory"
```

Anaconda Prompt uses the same Command Prompt commands. The explicitly selected
existing interpreter is authoritative; no environment installation is required.
If any candidate source or its maintained README changes after review, emit and
review a new source manifest. Do not reuse the old review SHA or broaden allowed
members to force a passing build.

Preparation status is established by the fresh private receipts, rather than
the existence of this source file. A package is prepared only after its actual
`BUILD_RESULT.json`, source closure and independent archive restoration verify.
Native deployment, real data recovery, portrait UX and sustained/accuracy
verification remain separate requirements.
