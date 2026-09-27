# N5 release preparation — campaign not complete

Latest machine-readable checkpoint: `N5_STATUS_20260927_V3.json`. It preserves
the earlier status and records accepted N2/N3, reviewed numerical N4 coverage,
the failed first actual application attempt, verified import repair, fresh timed retry and remaining N5 validation.

The preserved baseline is usable on Windows. N2/N3 have accepted offline
component handoffs. New N4-selected alternatives are not accepted yet: the
integrated application comparison and release-specific validation remain open.
This checkpoint must not be described as a completed N5 or campaign closure.

## Later Pi reconnection: baseline preparation

The Pi remains off during the campaign. These are later user-run steps; they
have not installed or validated anything on the device.

1. Confirm the actual device identity, 64-bit OS and transfer route. Use a USB
   mount path or the user's verified wired host/key, never a historical address.
2. Transfer the baseline archive listed below and the Git-verified companion
   `pi_storage_preflight_v1.py`. The companion is outside the immutable archive.
3. Follow `README_PI_STORAGE_PREFLIGHT_V1.md` for the read-only check, supplying
   the archive hash, actual install/data roots and a fresh output report. On the
   Pi require `PREREQUISITE_METADATA_PASS_ONLY` and `ESTIMATED_FIT` before the
   later install steps. Resolve missing prerequisites or space first. These
   statuses are metadata checks, not model/GUI functional validation.
4. Follow `INSTALL_CM5.md`: verify the extracted bundle, stage, health-check,
   explicitly activate, then launch idle. Keep personal data outside the release
   and retain the previous version; `UPDATE_ROLLBACK.md` gives rollback steps.
5. After reconnection, check each actually installed backend with saved audio,
   persistence and switching, and measure real CM5 resources. Follow
   `PI_RECONNECTION_REQUIREMENTS.md` and `WHEN_HARDWARE_ARRIVES.md` for remaining
   checks. Live audio/hardware tests require their later authorization.

The baseline space estimate is 2.80 GiB of additional free space including a
1-GiB reserve and an unmeasured 512-MiB runtime/filesystem overhead budget.
`PI_STORAGE_PREFLIGHT_CHECK_V1.json` records 11 passing tests and all 31 declared
bundle member hashes. Actual Pi free space is unknown. This estimate does not
cover additional backends or prove fit within the 2-GB RAM target.

The intended final delivery uses one shared GUI/backend picker and named
launchers for validated compositions, with optional assets when storage permits.
The current archive contains the baseline only. Optional backends are not yet
delivered as accepted Pi installations; unavailable choices must stay explicit.

## Current artifacts and Windows baseline

Windows shortcut: `Start-N5-BASELINE.cmd` in this directory. It delegates to the
unchanged N1 installed baseline with a separate campaign data root, opens idle,
and leaves the personal production store untouched. Do not run a second
inference session while the admitted numerical worker owns the machine budget.
Prepared O0 files already include their gain; O1 is unity. Choose saved mono
files explicitly. There is no microphone enumeration or automatic capture.

Private release directory:
`G:\Just_Peachy_N1\20260924_campaign\local\n5\releases`.

| Artifact | Contents | Actual status |
|---|---|---|
| `just-peachy-baseline-cm5-offline-v1.zip` | Existing immutable N1 application, 13 ARM64 CPython 3.11 wheels, eight exact baseline model/tokenizer assets, corrected install helpers | Prepared; every ZIP member read back and hashed; target install/model execution pending |
| `nemo-speech-arm64-engineering-v1.tar.gz` | Six newly cross-built ELF binaries, SONAME links, source/build pins and 12 notice files | ARM64_BUILD_VERIFIED; QEMU loader result separate; no models or selected application profile |
| Existing `just-peachy-n1-common-20260924-v1.zip` | Same baseline code for Windows/Linux | Earlier N1 Windows checks retained; not re-labelled as N5 full-bank acceptance |

`ARTIFACT_INDEX.json` records archive hashes. Do not upload the private offline
bundle, research evidence, profiles or model weights to GitHub. Native runtime
binaries stay outside Git as separately reproducible engineering artifacts.

The common front end remains 480×800 with the same modes, text/Unknown rules,
roster intent and rescue controls. See MODE_GUIDE.md and BACKEND_GUIDE.md.
No backend has a measured CM5 memory tier: 2GB is the target, not a result.
4GB/8GB alternatives may increase capacity but do not establish CPU speed.

Read INSTALL_CM5.md only when the device is connected later. Pins, host and keys
are intentionally unassigned. Hardware status: CM5_HARDWARE_NOT_TESTED and
NOT_LIVE_HARDWARE_TESTED. No denoising, new acoustic capture or human enrollment
ran. N5 does not stop upstream workers or their scheduled probes before closure.

For continuation, use N5_HANDOFF.md. Build/run commands, inputs and outputs are
in README.md and README_ARM64.md; the workbook proposal is WORKBOOK_UPDATE.md.
