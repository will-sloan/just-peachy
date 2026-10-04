# Conditional production14 from the exact frozen13 runtime

Purpose: prepare a reviewable release plan and pinned external builder without rebuilding from mutable runtime sources. `prepare_production14_plan.py` verifies every frozen13 member before and after preparation, validates the246 standard selection rows against its exact profiles module, and preserves the61 actual selected-asset facts. It maps only the one package-local component-review asset to the future14 path after checking its bytes. The other60 asset paths remain unchanged, including the exact installed interpreter exception already present in13.

The output is deliberately unusable as authorization: production acceptance is false, full-backup/desktop/evidence fields are empty, the relocation certificate is unreviewed, and the destination binding preview is disabled. No runtime package, archive, ZIP, native process, model or Desktop change is created. Historical production13 plans from source12 remain untouched.246 means supported default control combinations, not246 native experiments or qualified quality results. Optional parallel/provisional rows are absent. At most10 separately reviewed optional rows can fit the existing256-selection limit.

Inputs: exact disabled or later admitted13 snapshot plus manifest SHA; the SHA-pinned standard matrix and actual selected-assets-01 copy; the reviewed external prepare_package builder. Output: a fresh private production14-plan directory with non-authorizing JSON, disabled binding preview,13-field relocation mapping, exact source/asset provenance, pinned builder and five exact frozen13 import dependencies with independent backup/restore copies. All source code and descriptors used by a later build come from the exact snapshot, never mutable N. Acceptance ceilings proposed for review remain normal source300s/developer source3600s and maximum drain/backlog600s. Ordinary SessionPolicy defaults stay drain120s/backlog120s;600s is a ceiling for an explicit developer policy, not a ten-minute ordinary backlog default. These ceilings are not acceptance or sustained-session proof.

## PowerShell: prepare the conditional plan

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$old="$q/audit-preparation/production13-plan-fda43f06a54c42df9d75b9f8c556a446"
$source="$q/audit-preparation/saved-source-derivative-9080f3f053204c948d94b55922231ffc/package"
$sourceManifest='78d2a01002b72cf66816fe2382a34032cefe994d962ba3d627f6b3ad060ece7b'
& $py -B "$n/prepare_production14_plan.py" --source $source --source-manifest-sha256 $sourceManifest --matrix "$old/SUPPORTED_DEFAULT_SELECTIONS_REQUIRES_REVIEW.json" --assets "$old/SELECTED_ASSETS_ACTUAL_SOURCE.json" --builder "$n/prepare_package.py" --output-root "$q/audit-preparation"
```

The already prepared disabled-source plan is `Q/audit-preparation/production14-plan-d6b03cfe19924879b4b6a990711cb89a`. Content SHA is `5cae6376494d703a9600c020ebce725ed0f86999d1ed4ffa613a5f1485a0fd79`;317 source inventory members were verified. Before final production review, rerun with the exact **actual admitted13** snapshot/manifest used by the measurements. This changes source authorization provenance, not runtime content. The tool rejects another content identity. It does not rewrite any old measured proof as execution of14.

## Conditional final review and build sequence

1. Pin the actual13 package/binding, closed measurement and closure receipts. Review the changed saved/repeated100ms path, actual History Export04, optional first/follow-up and research outcomes with their proper scopes. Retain older unchanged-function evidence as such. Full-application hour04 failed at3584.955s and cannot support an hour pass. Neither optional nor research failures may be silently treated as production acceptance.
2. Require actual backup03 `FULL_BACKUP.json`, its complete source-finalization/owner/cgroup closure, full manifest and independently verified PC payload. Backup02's failed guard mirror and partial files do not qualify. Pin the selected original Desktop SHA from the same accepted full backup, and preserve all11 owned shortcuts/startup/calibration/settings members.
3. The root reviewer creates fresh `ACTUAL_PRODUCTION_ACCEPTANCE.json` from the reviewed standard rows/assets, exact target/content/installed-manifest/previous-Desktop pins and actual full-backup record. Required runtime schema is `just-peachy.v29.production-acceptance.v1`, with accepted=true, an identified reviewer and actual review time. This task does not issue that receipt. Optional true rows require exact normal measured references and a separately reviewed13-to14 reuse receipt retaining actual13 qualified binding/package/measurement/closure provenance; an unreviewed relocation preview or first-execution permit is insufficient. Keep optional references empty if that review does not pass.
4. After checking all13 path mappings and exact source/admitted binding pins, create a **fresh** `ACTUAL_RELOCATION.json` from the preview with reviewed=true, reviewer and review time. Do not modify the preview. Every non-path operational field must remain equal. The builder separately rechecks this, full backup and acceptance before output.
5. Run the pinned builder below. Then independently compare source/destination inventories: all runtime code, profiles, model/raw/batch references and source backup bytes must remain identical. Only BINDING target/13 authorized paths/four authorization fields, the package manifest target and new acceptance/backup/relocation metadata may differ. Do not stage if content SHA changes. Preserve any failure and use a fresh output directory; never edit13 or retry in place.

```powershell
$plan='<fresh actual-admitted13 production14-plan directory>'
$source='<exact actual admitted13 package used by the reviewed proofs>'
$sourceManifest='<its exact manifest SHA256>'
$certificate='<fresh actual reviewed ACTUAL_RELOCATION.json>'
$certificateSha=(Get-FileHash -Algorithm SHA256 -LiteralPath $certificate).Hash.ToLowerInvariant()
$acceptance='<actual reviewed ACTUAL_PRODUCTION_ACCEPTANCE.json>'
# This external builder and its import dependencies are pinned copies in $plan.
& $py -B "$plan/pinned-builder/prepare_package.py" --source $source --profiles "$source/profiles" --source-snapshot-manifest-sha256 $sourceManifest --release-id field-runtime-v29-build-14 --reviewed-relocation-certificate $certificate --relocation-certificate-sha256 $certificateSha --production-acceptance $acceptance --output-root "$q/audit-preparation"
if ($LASTEXITCODE -ne 0) { throw 'Production build not accepted; preserve failure and source' }
```

The existing builder retains the262144-byte acceptance limit,2MiB compressed staging gate, full-file source/hash checks, exact frozen options, full backup membership/readback, and existing independent source copies. It does not install or activate. Expected current plan is120438 bytes before final proofs/references; final actual output size must pass its checks. Do not override source/raw/variant options to make a build fit.

After verified production14 creation, root separately stages it through the reviewed current host dispatcher. [README_GUARDED_ACTIVATION.md](README_GUARDED_ACTIVATION.md) covers exact old-byte backup/restore and thin installer invocation. Then use [README_DESKTOP_CONSOLIDATION_V2.md](README_DESKTOP_CONSOLIDATION_V2.md), followed by exact Desktop Exec/native_scope idle/normal Exit last. No capture is needed for that final idle check. Runtime/startup remain unchanged until those actual operations are authorized by the completed evidence and performed by root.


The existing pure optional reuse API is `reuse_measured_admission(...)` in `../optional_first_dispatch_20261003/release_review_tools.py`, documented in that directory's `README.md`. Use exact frozen13 modules and original approved actual13 receipt/raw binding/manifest plus the reviewed14 relocation certificate. It changes only the operational-binding pin and adds explicit reuse_basis; actual qualified binding/package, measurement/closure/source fields and selected_asset_inventory_sha256 remain13 facts. Independently compute the selected14 asset subset and require equality with the original pin before issuing the14 reference. The planned Pyannote/TitaNet plus anonymous CurrentDelayed subset has26 assets with no package-local path, so the separate one-row thread2 mapping in the61-row base inventory is not an optional-proof rewrite. Any actual subset difference must fail; the helper does not silently admit it or re-relocate an already derived receipt. Exact optional input source, primary embedding, selection and policy remain limited to the actual measured proof.

## Command Prompt / Anaconda Prompt and focused checks

Enter `powershell -NoProfile`, then run the relevant complete block above. Use the exact qualified interpreter; no installation/environment change is needed. The plan command registers actual PID/Unix create_time/affinity[14] before project reads and checks C:50GiB/G:75GiB plus16MiB preparation capacity. The pinned builder has its existing early CPU14 owner and bounds.

For host-only checks use the CPU14/early-owner wrapper in README_STORAGE.md with `test_production14_plan`. The two focused checks ensure the actual unaccepted plan cannot authorize/relocate, and that the reviewed relocation validator accepts only the13 exact path fields while rejecting a source-geometry change. Synthetic review exists only in test memory and is never written as actual authority. No native run, model import, archive or acceptance is produced by those checks.
