# Installation, health and recovery

> Current October3 update: **v28, desktop-first startup**. Use the ten desktop
> shortcuts; choose **Exit to desktop** in the main manager to close normally.
> Four recording slots remain. See [DESKTOP_GUIDE.md](DESKTOP_GUIDE.md) and
> DESKTOP_RELEASE_INDEX.json. Earlier v27 measurements below remain historical.

The deployed release is `/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v28`, with profiles/shortcuts in the sibling `field-runtime-v28-profiles`. It is a deployable overlay for this prepared CM5, not an SD image for arbitrary devices.

The existing aarch64 Python3.11 baseline environment, installed v12 application, local Sherpa/PnC/Pyannote/ReDimNet assets, selected Nemotron libraries/endpoints and research dependency pins remain required. TitaNet reuses the prior88696429-byte ONNX/frontend/manifest export at `runtime-titanet-v3`. No first-run downloads occur. The retained native dependency catalogue covers7890entries/7847unique files/791871486bytes; later runtime/endpoint/TitaNet pins supplement it. Do not move those native paths or assume the small ChatGPT ZIP contains models.

Current source/control backups and independent restores are under `field-runtime-v28-install` in the private PC base listed in PATHS_AND_BACKUPS.md. `stage-backup` and `stage-restore` preserve installed code/profiles; `active-backup` and `active-restore` preserve startup/config changes. The historical v23 prepared-device kit includes its old code, TitaNet assets, operator sources and exact manifests; it does not include mounted motion. The v27 install backups and motion source/capsule are the current restore basis. Its BACKUP.json certifies independent ZIP and expanded-file readback. Older baseline/model archives remain separate.

## Normal operation and health

Open one version28 profile shortcut. The manager must show capture off and its remaining slots, at480×800. Starting a recording verifies pinned model/runtime/profile membership, current owners, units, capture leases, storage and process limits before acquisition. Missing/incompatible assets or a pending writer fail explicitly; there is no silent model fallback or download.

Current limits retain CPU2/3 shared200%,64tasks, one model thread, GPU off,1MiB stacks and default768MiB address space. Minimum start memory850MiB and stop floor192MiB remain. The32GB device must retain5GiB free; PC C/G floors are50/75GiB. Four recording slots and independent local/PC copies are reserved in full, even when Audio off or a short/failed run uses fewer bytes.

## Renewal and rollback

Use DESKTOP_GUIDE.md for the current desktop-aware installer/binder and renewal constraints. The old renewal wrapper must not be replayed unchanged.

The rollback shortcut is `just-peachy-field-runtime-v28-rollback.desktop`. Finish Stop/Save/Return and close the idle manager before using rollback. Its pinned local path restores the backed-up baseline with login autostart still disabled; it does not erase data or undo personal settings. Baseline auto-listening remains false. Actual local automatic rollback and normal startup-command restart passed in the retained candidate16/17 evidence. No arbitrary crash/power-cut durability claim follows.

If a guard rejects or a session fails, keep every original and failure receipt. Stop/Close through the app and preserve the failed source via the maintained failure-preservation instructions; do not remove pending files, reset counters or rerun a failed output. A measured metadata-only continuation allows at most1088 prior identities under the unchanged256KiB request ceiling; all old identities and other finite bounds remain explicit; renewal can refuse when a review is required. Do not bypass that refusal.

Use copies in new directories for restoration review. Verify all file sizes/SHA256 against the manifest before a fresh-version deployment. Never unzip an old consumed release over the live manager or blindly replay an expired research dispatcher.

Mounted sensor configuration is `/home/peachyprototype/JustPeachy/data/imu_config.json`.
Its fixed geometry and library hash are pinned. Stale/unavailable sensor data
suspends location trust; do not fabricate a corrected direction. Source25's graphic
failure and26's AEC255 firmware fault were preserved. One conditional maintenance
send followed that actual fault; matching firmware readback and the v27 recording
succeeded. No periodic reset is configured or authorized. See MOTION_GUIDE.
