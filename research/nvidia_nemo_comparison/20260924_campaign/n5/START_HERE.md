# N5 release preparation — campaign not complete

The preserved baseline is usable on Windows. New N4-selected alternatives are
not accepted yet: N2/N3 execution and the N4 full comparison remain prerequisites.
This checkpoint must not be described as a completed N5 or campaign closure.

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
