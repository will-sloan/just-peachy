# Installation, health and recovery

The deployed release is `/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v23`, with profiles/shortcuts in the sibling `field-runtime-v23-profiles`. It is a deployable overlay for this prepared CM5, not an SD image for arbitrary devices.

The existing aarch64 Python3.11 baseline environment, installed v12 application, local Sherpa/PnC/Pyannote/ReDimNet assets, selected Nemotron libraries/endpoints and research dependency pins remain required. TitaNet reuses the prior88696429-byte ONNX/frontend/manifest export at `runtime-titanet-v3`. No first-run downloads occur. The retained native dependency catalogue covers7890entries/7847unique files/791871486bytes; later runtime/endpoint/TitaNet pins supplement it. Do not move those native paths or assume the small ChatGPT ZIP contains models.

Current source/control backups and independent restores are under `field-runtime-v23-install` in the private PC base listed in PATHS_AND_BACKUPS.md. `stage-backup` and `stage-restore` preserve installed code/profiles; `active-backup` and `active-restore` preserve startup/config changes. The final private prepared-device kit includes code, TitaNet assets, operator sources and exact manifests. Its BACKUP.json certifies independent ZIP and expanded-file readback. Older baseline/model archives remain separate.

## Normal operation and health

Open one version23 profile shortcut. The manager must show capture off and its remaining slots, at480×800. Starting a recording verifies pinned model/runtime/profile membership, current owners, units, capture leases, storage and process limits before acquisition. Missing/incompatible assets or a pending writer fail explicitly; there is no silent model fallback or download.

Current limits retain CPU2/3 shared200%,64tasks, one model thread, GPU off,1MiB stacks and default768MiB address space. Minimum start memory850MiB and stop floor192MiB remain. The32GB device must retain5GiB free; PC C/G floors are50/75GiB. Four recording slots and independent local/PC copies are reserved in full, even when Audio off or a short/failed run uses fewer bytes.

## Renewal and rollback

Use the PC `Refresh-JustPeachy.ps1` commands in MODE_GUIDE.md/README_RUNTIME_OPERATOR_V2.md. It preserves all healthy completed recordings and the manager, independently reads back the PC copies, restores the idle baseline, inspects actual current ownership/resources and installs a fresh version. New version IDs and roots are mandatory. Existing complete22→23 renewal passed. The one-command wrapper's plan was checked without another model run.

The rollback shortcut is `just-peachy-field-runtime-v23-rollback.desktop`. Finish Stop/Save/Return and close the idle manager before using rollback. Its pinned local path restores the baseline startup; it does not erase data or undo personal settings. Baseline auto-listening remains false. Actual local automatic rollback and normal startup-command restart passed in the retained candidate16/17 evidence. No arbitrary crash/power-cut durability claim follows.

If a guard rejects or a session fails, keep every original and failure receipt. Stop/Close through the app and preserve the failed source via the maintained failure-preservation instructions; do not remove pending files, reset counters or rerun a failed output. The1024prior-owner and other finite bounds remain explicit; renewal can refuse when a review is required. Do not bypass that refusal.

Use copies in new directories for restoration review. Verify all file sizes/SHA256 against the manifest before a fresh-version deployment. Never unzip an old consumed release over the live manager or blindly replay an expired research dispatcher.
