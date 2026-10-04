# Current release/data backup before one-shortcut activation

Purpose: reconcile a fresh native census with verified existing private PC
backups, transfer only bytes not already available, and produce the complete
independently verified release/user-data backup required by production
acceptance. `launch_backup_action.py`, `native_backup_guard.py`,
`native_backup_probe.py`, `reconcile_production_backup.py`, and
`backup_reconciliation.py` implement this workflow using the existing strict
SSH monitor and host admission. They make no native call merely by importing
or testing them. The operator commands below do contact the admitted device;
none were run during preparation. No desktop or autostart setting is changed.

## Exact scope and existing local seeds

The reviewer must name the current native paths from the fresh installed
binding/desktop and data census. Scope includes the retained v27 and v28 source,
profile/configuration and calibration/routing files, the one existing desktop
launcher and its restoration files, all current operator recordings with their
indices/metadata, and current speaker galleries/enrollment metadata. Explicitly
include any newer operator data root used by the candidate. Do not infer absence
of recordings or gallery data from an old source-only mirror. Do not replace
this scope with raw/pipeline benchmark outputs.

These existing PC roots were found and are useful **candidate byte sources**:

```text
G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-runtime-v27-install
G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-runtime-v27-preservation-desktop-v1
G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-runtime-v28-install/stage-backup/field-runtime-v28
G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-runtime-v28-install/stage-backup/field-runtime-v28-profiles
G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12
```

Their existence is not proof of current native equality or complete personal
data coverage. Reuse a file only after hashing its actual PC bytes and matching
the fresh native relative path, byte count and SHA256. Preserve original backup
roots unchanged. Large immutable model/library assets may be listed separately
by exact content-addressed path, resolved path, bytes and hash in production
`assets`; do not recopy them merely to duplicate an already verified immutable
asset store. The source/configuration needed to select and restore them remains
inside the reviewed release/data scope.

The preserved v27 `RELEASE.json` names recording roots v10108–v10111;
v28 names v10112–v10115. Include those current roots plus any subsequent
recordings and current galleries identified by the actual configuration.
The source-only `SOURCE_ASSET_BACKUP.json` is not a personal-data census.
`JustPeachy/data/live_config.json`, `settings.json`, the current install
selector, exact desktop launcher/restoration files and `.config/kanshi/config`
must be considered explicitly. No missing path is silently skipped.

## Census, missing-only transfer, and complete readback

1. Obtain a fresh full process/lease baseline through `host_operations.py`. Close actual project/native/GUI
   owners and prove exact source and service closure. Acquire only the reviewed
   research/file-snapshot exclusion needed to keep the named scope stable; never
   start capture or alter source routes. Pin the boot, actual owner and unit.
2. The finite `native_backup_guard.py` enumerates only the explicit
   source roots/files. For every regular single-link member record a normalized
   relative restoration path, original absolute source path, device/inode,
   bytes, modification/change timestamps, and streamed SHA256. Record the
   roots and all excluded immutable asset pins separately. Reject symlinks,
   traversal, duplicate restoration paths and scope changes. Empty directories
   and permission/mode requirements need an explicit restoration inventory.
3. On CPU14, compare those rows with the existing seed roots. Match by actual
   file content/extent and recorded native mapping, not filename alone or an
   old manifest claim. Output a reviewed reconciliation plan with `reuse` and
   `missing` rows, total full-backup bytes and missing-transfer bytes. No file
   from outside the census becomes an implicit backup member.
4. Reserve a fresh private destination for the **entire** backup and an
   independent complete copy/readback. Preserve C:50GiB/G:75GiB host floors and
   the native5GiB/fraction floor; derive finite counts, byte allowances and
   transfer windows from the census before copying. Preparation remains its
   separate16MiB scope. Do not force an unknown-size full backup into the tiny
   raw qualification or GUI job allowance.
5. `reconcile_production_backup.py` materializes matching bytes from existing PC seeds into the new backup root
   using bounded streaming copies, never hardlinks or moves. Transfer only the
   `missing` native bytes with the existing owned bounded chunk-copy protocol;
   each request binds the exact member identity/hash/offset and refuses changed
   source files. Do not create another full native copy unless the reviewed
   snapshot/copy interface specifically requires and reserves it.
6. Re-census the named native membership/identities after transfer, preserving
   the exclusion until the checks finish. If any member changed, retain the
   failed attempt and reconcile that member under a fresh admission; never
   label a mixed-time snapshot complete. Independently rehash **every** final
   PC file, including reused files. Compare full membership and total bytes.
7. The reconciler publishes the original source census, reconciliation/reuse provenance, exact
   native owner/unit closure and host readback as durable receipts outside the
   payload root. Only the actual verified native/host tool may publish its
   `COMPLETE` result. Do not synthesize one from a list of successful copies.
8. Feed the exact accepted backup pins into the production gate below. Leave
   all old packages, previous desktop backups and original recordings intact.
   Activation/rollback follows `README_DESKTOP_ACTIVATION.md`; this backup
   workflow starts nothing and changes no desktop/autostart/rotation setting.

## Existing production verifier contract

`prepare_package.verify_full_backup` currently expects:

- `full_backup.scope` exactly `selected-release-and-user-data`;
- a concrete `root` containing every payload file and no unlisted files;
- separate `manifest_path`/`completion_path` with exact SHA256 pins;
- a manifest list of1..4096 normalized relative members, each with `path`,
  `identity.bytes`, and `sha256` (additional source identity fields can remain);
- actual completion `kind:COMPLETE`, `mirror_scope:all_regular_output_files`,
  exact file/byte counts, canonical manifest SHA256, and closure flags
  `closed`, `exact_owner_gone`, `cgroup_empty` all true.

The builder reopens and rehashes every PC member and rejects extra files.
Receipt files therefore stay outside `root`. The native installer's production
gate also binds the exact previous desktop SHA and complete backup pins.
If the real census exceeds4096 members, the current verifier is insufficient:
review an explicitly bounded extension before transfer/acceptance; never omit
files to make the count fit. Native completeness and backup scope are reviewer
decisions backed by the census, not claims made by source-file presence.

## Inputs, outputs, PowerShell, CMD and Anaconda

Inputs: fresh exact native scope/current census, immutable owner/closure proof,
explicit existing-PC seed mappings, reviewed byte/count reservations, and the
selected production acceptance. Outputs: reconciliation plan, missing-only
transfer receipts, complete payload root, full manifest/completion/readback,
   and the production verifier result. No transcript/audio contents need printing.

The action payload supplies `package`, `package_manifest_sha256`, actual
`boot_id`, fresh `expires_unix` within600 seconds, a fresh
`label: production-backup-01`, `maximum_output_bytes: 16777216`,
`full_backup_reservation_bytes`, `backup_scope`, and its canonical JSON SHA256
`backup_scope_sha256`. The package must contain the new backup modules and
reviewed shared helper; build07 does not acquire them by an in-place update.
This is staging/admission of code, not production shortcut activation.

`backup_scope` has schema `just-peachy.production-backup-scope.v1`,
`reviewed: true`, `roots` with exact `source` and normalized relative
`destination`, `external_assets` with exact `path`, `resolved_path`, `bytes`
and `sha256`, `maximum_payload_bytes`, `maximum_external_asset_bytes`, and
`runtime_seconds` from180 to3600. Full payload reservation must exactly match
the action's `full_backup_reservation_bytes`. The code never guesses a32GB
device capacity or automatically excludes large files. Scope is constrained
to explicit campaign/data/config descendants, the current install selector,
the exact kanshi configuration and individually named desktop files.
Overlapping roots/aliases, symlinks, special files, hardlinked source files,
unsafe or Windows-incompatible names, and case collisions are refused.

The separate seeds JSON is a list of `{ "destination": "relative-alias",
"local": "absolute-existing-PC-seed" }` prefix mappings. Use actual inspected
paths from the seed list above. Missing or stale bytes are fetched; existing
seed files are never modified or removed. Seed matching rehashes actual bytes.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$packageCopy=Read-Host 'Exact independently verified PC copy of the admitted package'
& $py -B "$n\host_operations.py" --label production-backup-01 --action "$n\launch_backup_action.py" --payload "$q\production-backup-01-PAYLOAD.json" --writes
# Preserve the returned actual action_result as production-backup-01-JOB.json.
& $py -B "$n\reconcile_production_backup.py" --job "$q\production-backup-01-JOB.json" --package-copy $packageCopy --seeds "$q\production-backup-01-SEEDS.json" --output "$q\production-backup-01-reconcile-01"
```

In **Command Prompt or Anaconda Prompt**, set `N`, `Q`, `PY` to the same exact
values and `PACKAGE_COPY` to the actual independently verified package root:

```bat
"%PY%" -B "%N%\host_operations.py" --label production-backup-01 --action "%N%\launch_backup_action.py" --payload "%Q%\production-backup-01-PAYLOAD.json" --writes
"%PY%" -B "%N%\reconcile_production_backup.py" --job "%Q%\production-backup-01-JOB.json" --package-copy "%PACKAGE_COPY%" --seeds "%Q%\production-backup-01-SEEDS.json" --output "%Q%\production-backup-01-reconcile-01"
```

Both entrypoints set CPU14 and publish the actual PC owner before project/data
reads. Native preparation stays16MiB; the complete PC payload has its separate
explicit capacity reservation. Reconciliation checks the full reserve before
its first SSH, limits each metadata receipt/census, retains at most4MiB of
snapshot transfer receipts within its separate16MiB preparation scope, and
uses16KiB frames with adaptively measured segments no larger than1MiB.
Each helper is CPU3/128MiB AS/1MiB stack/15seconds. Only the explicit finalize
mode may create its one16KiB-bounded marker. The guard is in the existing
CPU2–3/200%/64-task service, narrows itself to128MiB, holds the actual research
and hardware flock leases without starting capture, and expires automatically.
The probe checks actual kernel flock PID/device/inode, process start ticks,
boot, systemd invocation and cgroup before and after each source read.

Outputs are `CENSUS.json`, `RECONCILIATION.json`, the fresh `payload/`,
per-phase actual owners/SSH closure/readback receipts, and a normal complete
`guard-monitor/` mirror. The source guard rehashes all membership, identities,
content and external pins after finalization while exclusion remains held.
Only after its natural successful exit and actual empty cgroup does the PC
reconciler independently rehash every payload member and publish
`MANIFEST.json`, `COMPLETE.json`, `FULL_BACKUP.json` and `RESULT.json`.
`FULL_BACKUP.json` can be used verbatim for the production acceptance field;
`prepare_package.verify_full_backup` performs another independent readback.
`FAILURE.json` never grants completion; partial data and old backups remain.
The native guard is never signalled by the reconciler; failure leaves its
bounded timeout in place and requires actual closure before another admission.

`host_operations.py` recognizes only the exact named nested
`production-backup-NN-reconcile-NN/guard-monitor/RESULT.json` as an additional
normal closed-mirror location. Its existing unit-reference decoder remains
path/schema/hash/job/closure-bound. The actual historical scanner visits
`*OWNER*.json`; the new snapshot reference receipts have no OWNER in their
names and are not treated as extra processes. The true guard `OWNER.json`
retains exactly `pid`, `start_ticks`, `boot_id`.

Host tests: use the early CPU14 fsynced `REGISTERED_OWNER` wrapper in
`README_STORAGE.md`, replacing `test_storage` with
`test_backup_reconciliation`. The tests cover31-independent-session storage
elsewhere; these new checks focus on seed mismatch, scope/asset mutation,
capacity/path isolation, active-snapshot framing without false closure, actual
next native ownership-precheck decoding, and compatibility with the real
production full-backup verifier. No SSH/model/capture runs in these tests.

The production verifier and activation commands are in
`README_RELEASE_AUTHORIZATION.md` and `README_DESKTOP_ACTIVATION.md`. Existing
user authorization remains valid; each native execution still needs fresh
machine-state admission. A fresh production census/full backup has not been
performed by this subagent. Current recording/gallery completeness remains
unclaimed until the actual scoped evidence exists.

The earlier source-only codec projection of150.9MB/hour against approximately
161MB/hour SQLite allowance is a narrow margin, before combined caption and
health variation. This backup work does not change that allowance or convert
host timing into Pi evidence. Measure actual native300s/hour SQLite, event,
audio and export growth before production admission; see `README_STORAGE.md`.

## Exact startup files added to the reviewed native scope

The native guard and transfer probe share the same path validation. Include
these two individually named files in the production `roots`, with unique
restoration aliases (do not select all of `.config`):

* `/home/peachyprototype/.config/autostart/just-peachy.desktop` —427bytes,
  SHA256 `8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206`.
* `/home/peachyprototype/JustPeachy/start-prototype.sh` —405bytes,
  SHA256 `79b7b08db6a67060bfc20a02ae8af437b37a938eb1f4e33817adcdb33d57f19f`.

These pins are from actual post-soak-baseline02. The autostart file remains
disabled; backup never changes it. Both exact byte copies are mandatory when
selected and may not be excluded as external immutable model references. A
changed current byte/hash fails this scope and requires a reviewed fresh pin.
The guard checks before publishing its census; the read probe checks the same
paths/pins before any catalog or segment transfer. Parent directories, sibling
startup scripts and unrelated configuration remain outside scope. Existing
`field-runtime-v28-galleries` under the campaign is supported as an explicit
root. Include every one of the11retained Desktop shortcut files individually
in the production scope before any separately authorized consolidation.

PowerShell, Command Prompt and Anaconda commands above are unchanged; add
these roots to the JSON input rather than any new command flags. Focused host
checks use `test_backup_reconciliation.BackupTests.test_native_exact_startup_files_without_broadening_config`
with the same CPU14 early-owner wrapper. This prepares support, and is not a
claim that a complete current native backup has been made.
