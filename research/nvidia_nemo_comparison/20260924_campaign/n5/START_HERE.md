# N5 release preparation - campaign not complete

Latest checkpoint: `N5_STATUS_20260927_V16.json`.

For working Windows NeMo previews, use `Start-N5-NEMOTRON.cmd` (A2 captions)
or `Start-N5-NEMOTRON-SPEAKERS.cmd` (A2 plus D1 anonymous speakers).
Both open idle and use a separate campaign data store. Optional `--wav` accepts
an already-prepared saved file; microphone/playback remain disabled. Read
`README_NEMOTRON_WINDOWS_PREVIEW_V1.md` before launch. Both modes passed their
own real Windows render/save/reopen/delete checks on one complete 44.7-second
source. All four private GUI processes closed normally. A2's main-bank WER is
13.34% versus baseline 14.92%, with increased omissions and a short-turn
weakness. Read `COMPONENT_PERFORMANCE_REPORT_20260927.md` for the full accuracy
and processing comparison, including all sixteen combinations and Nemotron's
verified CPU bottleneck. `NEMO_RESULTS_AND_INSIGHTS_20260927.md` adds ASR strata.
No visible application was launched by the campaign.

N4 actual application
confirmation is PARTIAL: V10 has two collected cells pending acceptance, two
failures and 236 unattempted of 240. The D1 speaker lane exceeded its drain
limit; the fourth cell also failed Controller closure. Exact process owners
have exited and failed evidence is preserved. No further whole-panel rescue is
scheduled during this campaign. Read `../n4/N4_PARTIAL_REPORT_20260927.md` and
`../n4/APPLICATION_PANEL_CLOSURE_FAILURE_V10.json` for the reconciled evidence.
No new release profile is accepted.

The compiled ARM64 native harness passed eight malformed-WAV checks. Its
saved-audio run ended at the unchanged A2 time limit during the repeat pass;
A3 was unattempted. A2 completed the first full source, but state parity and
forced-endpoint checks remain unverified. Zero complete model passes are
claimed. `NATIVE_STREAM_MODELS_PARTIAL_V1.md` records the preserved failure and
verified process closure. ARM64 GUI and CM5 validation remain incomplete.

The separate baseline ASR comparison also failed under QEMU: its Windows
reference passed, but both ARM64 full saved streams returned empty text despite
consuming and closing the source. No paired parity or complete ARM64 component
pass is claimed. All owners closed and the 14 bound sources were reverified.
See `BASELINE_ARM64_ASR_CHECK_V1.json` and `BASELINE_ARM64_ASR_FINDINGS_V1.md`.
The cause needs isolation; no unchanged retry or altered acceptance gate is used.

The later paired C++ diagnostic reproduced the ARM64 empty output on a fresh
recognizer while Windows produced three finals. Decoded samples, effective
configuration and Sherpa version/revision matched. Both jobs closed normally;
all source bindings and exact process closure were independently verified.
Read `BASELINE_C_API_DIAGNOSTIC_FINDINGS_V3.md` and its CHECK receipt for the
bounded runtime/emulation investigation. Diagnostic completion is not ASR
acceptance. No worker remains active at this checkpoint.

`BASELINE_WINDOWS_LIFECYCLE_CHECK_V1.json` adds a passing baseline smoke from
two real Windows processes on private desktops: 480×800 Tk rendering of the
same 31 segments, three persisted utterances across process restart, and
save/open/delete of only the test session. The synthetic people sentinel was
preserved; all owners closed normally and input desktop stayed unchanged.
Commands used the production Controller and GUI page methods; no physical
touch, mouse/keyboard operation, full-bank timing or optional backend pass is
implied. Purpose and run instructions are in
`README_BASELINE_WINDOWS_LIFECYCLE_V1.md`.

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

The currently evaluated optional A1/A2/A3/D1/E1 model/configuration assets total
1.97 GiB beyond the baseline's 0.20 GiB of model assets, counting shared hashes
once. OPTIONAL_BACKEND_STORAGE_ESTIMATE_V2.json records all 19 rechecked asset
hashes and separate totals. This is an asset-size estimate: optional ARM64 runtime,
transfer/extraction/rollback copies and personal data still need space. Several
choices may therefore be practical to store, but actual Pi free space and 2-GB
RAM fit must be checked separately. No optional Pi release is accepted yet.
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
in README.md and README_ARM64.md; the current workbook proposal is
WORKBOOK_UPDATE_20260927.md. The original WORKBOOK_UPDATE.md is historical.

`CAMPAIGN_COVERAGE_20260927.md` reconciles note, numerical, application and target
coverage. `RELEASE_MAPPING_20260927.md` maps the retained artifacts to their
immutable source/preparation tags. `HANDOFF_SELECTION_V2.json` selects 55 small
reports/tools plus this checkpoint's status; the reviewed packager adds the
selection, hash manifest and current Git backup receipt for 59 readable files.
Use `README_REVIEWED_HANDOFF_V2.md` to build a fresh private analysis archive
after verifying the selected bytes are committed and backed up. This partial
handoff is separate from the deployable software archives and does not close N5.
