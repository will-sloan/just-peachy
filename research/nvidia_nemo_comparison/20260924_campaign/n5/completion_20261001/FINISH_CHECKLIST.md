# Final delivery checklist

Delivery is INCOMPLETE. Hard deadline: 2026-10-01 16:14:58 UTC. Automation is paused. No further native work is scheduled.

Each item below retains its concrete exit criterion. A scoped pass does not complete an unmet final-release requirement.

## F01 — Verify the returned Pi

Status: **DONE**

New boot, exact launcher/app identities, unchanged install/live/display pins, XMOS device and actual display270 recorded.

Evidence: user-reconnect-20261001-v4/RESULT.json

## F02 — Return the existing app to safe idle

Status: **DONE**

One normal Stop; capture closed, hardware lease free, UI returned to Start; app and recordings preserved. ALSA1284 is a thread of app1124, not a separate source process.

Evidence: final-delivery-normal-stop-v1/RESULT.json; final-delivery-stop-completion-v1/RESULT.json

## F03 — Disable automatic listening

Status: **SAVED_NOT_REBOOT_TESTED**

Settings backup and independent restore verified; normal UI changed only auto_start_listening to false; saved hash verified. Final-release restart/boot persistence is F19.

Evidence: final-delivery-idle-start-v2/RESULT.json

## F04 — Finish the persistent local manager

Status: **PARTIAL_NATIVE_INTEGRATION_PASS_MANUAL_ENTRY_OPEN**

Wire the prepared initializer, broker, finish/reopen, census/export receiver and exact owner closure into one local manual entry. Bind current boot/PID identities, preserve full617760944-byte qualification reservation, and require complete local/PC copies before another slot. No consumed research launcher or expired policy as a user entry.

Evidence: CHECK_SUMMARY_V141; native reserve/run/finish/localbackup/reopen plus separate full PC copies. Persistent manual entry remains missing.

## F05 — Issue and enforce the production recording/lifetime policy

Status: **OPEN**

Measure current target+PC usage; allocate finite recording count/duration, launch/recovery slots and independent backups. Show limits and exhaustion in the app. Keep CPU/RAM/disk floors, first-fault latch, capture-off startup and explicit Start; no silent cap removal or replenishment.

Evidence: Missing; remains open.

## F06 — Install the selected backend compositions

Status: **OPEN**

One frontend with baseline, Sherpa ONNX/PnC+Nemotron-3 D1+compatible ReDimNet, and an explicit anonymous choice where supported. Pin actual executed model/runtime/buffer/gain/tap manifests. Keep live Delayed and saved Streaming/Chunk52 availability distinct; unavailable choices explain why and never silently fall back.

Evidence: Missing; remains open.

## F07 — Create real desktop profile shortcuts

Status: **OPEN**

Named Pi desktop entries select those manifests through the same versioned manager, start idle and exclude duplicate app/microphone/model owners. Verify each retained shortcut's actual launch; retain baseline/rollback entry.

Evidence: Missing; remains open.

## F08 — Complete manual Start/Stop/Return and repeated sessions

Status: **OPEN**

From the final user entry, verify New, consent, Start, Stop/drain, Save and Return; a subsequent recording gets fresh process ownership and preserves the first. Reuse old scoped component evidence; test the changed final composition once.

Evidence: Missing; remains open.

## F09 — Finish failure recovery

Status: **OPEN**

Verify missing/corrupt backend asset, startup failure and one interrupted/failed session in the final manager. Stop before diagnostics, release actual source/model/writers, preserve partial data, fence unresolved owners and provide a usable recovery/rollback path without resetting old failed ledgers.

Evidence: Missing; remains open.

## F10 — Finish the480x800 UI and nonempty captions

Status: **OPEN**

All required controls reachable with270orientation; correct backend/mode, recording state and unavailable reasons visible. Use an existing authorized saved speech input for actual nonempty captions/audio links, Pending/Unknown and independent caption timing. No audible playback or solicited speech.

Evidence: Missing; remains open.

## F11 — Verify saved history and data actions in the final release

Status: **OPEN**

Save/reopen two recordings, select earlier history, export/import and delete only a verified disposable copy after backup. Preserve complete audio/events/probabilities/timestamps. Existing V123/V128 passes are reused; rerun only final-entry integration or changed nonempty-content gaps.

Evidence: Missing; remains open.

## F12 — Verify personal gallery compatibility

Status: **OPEN**

Read-only review of UUID/encoder/revision/tap/gain namespaces and schema migration/rollback compatibility. Compatible references load; incompatible/empty galleries clearly stay Unknown. Preserve profiles/photos/vectors; no enrollment or reinterpretation of old vectors.

Evidence: Missing; remains open.

## F13 — Add optional processed recording controls

Status: **OPEN**

Provide Off/Processed selection before Start, recording indicator, elapsed time, admitted remaining duration/storage and Stop. Save exact model-input audio losslessly with its rate, channels, tap, gain and resampling metadata.

Evidence: Missing; remains open.

## F14 — Resolve true raw microphone support

Status: **OPEN_CONDITIONAL_HARDWARE_CAPABILITY**

Check actual firmware/routing for simultaneous physical MIC0-MIC3 and processed taps. If supported, qualify one bounded paired recording with synchronized clocks, sample counts and route restoration. If unsupported, visibly disable Raw+processed with the exact reason; never relabel O0/O1 or float/WAV as raw microphones.

Evidence: V141 actual firmware3.2.1/4reported mics/8channel endpoint/O0processed route; simultaneous rawMIC0-MIC3 NOT_QUALIFIED, unsupported hardware not proven.

## F15 — Close recording integrity and storage accounting

Status: **OPEN**

Bound every writer and count raw/processed/events/metadata plus independent local and PC copies. Enforce at least5GiB Pi/C50GiB/G75GiB free floors, finite duration, no drop/overflow masquerading as success, complete Stop/closed files and final manifest hashes. Preserve partial failures and originals.

Evidence: Missing; remains open.

## F16 — Deliver verified copy-to-PC offload

Status: **OPEN**

A reusable documented export command/control copies a stopped recording into a fresh private PC destination. Verify membership, sizes, SHA256 and full readback; retain receipt and path. Preserve interrupted transfers and Pi originals; no automatic deletion.

Evidence: V141 complete private broker and independent manager copies passed; reusable production operator offload flow remains OPEN.

## F17 — Finish deterministic install and health checks

Status: **OPEN**

Versioned code/config/runtime manifests; all pinned assets already local; native aarch64/runtime/dependency identity verified. Health reports missing assets, incompatible gallery, disk limits or unavailable hardware explicitly and never downloads on first use.

Evidence: Missing; remains open.

## F18 — Verify activation, rollback and local recovery

Status: **OPEN**

Back up active code/config/desktop/autostart manifests with independent restore readback. Activate final candidate, exercise rollback and restore candidate. Prove recovery works locally before denying its network access; preserve baseline and personal data.

Evidence: Missing; remains open.

## F19 — Verify final startup and offline operation

Status: **OPEN**

Final shortcut and one final-release restart/coldboot open idle with270orientation and no automatic listening. Exercise its supported operation with external network unavailable after local recovery is proven. Distinguish software network denial from physically unplugged testing.

Evidence: Missing; remains open.

## F20 — Run one bounded final recording/resource acceptance

Status: **OPEN**

Use the final installed composition for its supported bounded recording duration, then Stop/Save/PCcopy. Record combined resource/CPU/available-memory/disk observations, complete samples/events and actual cleanup. Reuse this same run for F08,F13,F15,F16 where it supplies evidence; no independent duplicate healthy runs.

Evidence: Missing; remains open.

## F21 — Declare camera, IMU and physical-control capabilities

Status: **DONE_CAPABILITY_DECLARATION_PHYSICAL_TESTS_OPEN**

Retain one actual hardware profile and exact known routes/pins; keep unknown GPIO disabled. Show optional/on-demand camera and IMU availability honestly, with axes/clock/motion limits. No invented pin mapping or unmeasured physical-touch/button pass.

Evidence: HARDWARE_CAPABILITIES.json; actual audio/display, explicit unqualified camera/IMU/buttons/raw.

## F22 — Freeze versioned artifacts and reconcile all original requirements

Status: **DONE_RECONCILED_WITH_GAPS**

Map every retained Windows/Pi composition to its actual source/config/runtime/model hashes and Git ref. Reconcile N1-N5, all34methods and full240-cell N4 denominator with existing receipts. Mark unrun/failed/deferred entries explicitly; no new campaign or benchmark sweep to fill them.

Evidence: FINAL_COVERAGE.md; original N5,73notes,240scene/panel denominators and all34methods retained; FINAL_ARTIFACT_INDEX.json.

## F23 — Finish the operator documentation

Status: **DONE_CURRENT_STATE_DOCUMENTATION**

Exact Start Here, named shortcuts, shared Mode/Backend guides, recording/offload instructions, Enrollment Compatibility, Install/Health, Update/Rollback, Licence Ledger, hardware template, paths/backups and troubleshooting. Include PowerShell/CMD/Anaconda commands for every new code path and supported limits/latency.

Evidence: Final operator guide, coverage, capabilities, artifact index and current guides; required functional gaps explicit.

## F24 — Finish the noisy-environment testing kit

Status: **DONE_PROTOCOL_ONLY**

Consent/privacy instructions, test scenes, reference/ground-truth method, timing/sample/route metadata, expected controls, naming/Unknown/overlap checks, failure rubric and run/results template. Actual noisy-human quality and physical-touch observations remain future measurements until performed.

Evidence: FIELD_VALIDATION.md/FIELD_RUN_TEMPLATE.json; no human/physical/noise-quality result.

## F25 — Create and verify the final private and Git backups

Status: **SCOPED_BACKUPS_DONE_PRODUCTION_RESTORE_OPEN**

Final deployable release/config and private recordings have complete independent copies/hash/readback and a demonstrated restore path. Push only reviewed small source/manifests/redacted reports; verify remote branch/profile refs. Never publish audio, profiles, vectors, credentials or model weights.

Evidence: Native full local/PC copies and source/private/index/remote publication verified; production activation/restore remains open.

## F26 — Build the final handoff and leave a safe device

Status: **DONE_HANDOFF_INCOMPLETE_DELIVERY**

Condensed ChatGPT ZIP<=20MiB(target<=10), WORKBOOK_UPDATE and artifact/hash index; deployable assets separately. Update ACCEPTANCE with actual evidence and all remaining blockers; close owned research, pause automation by deadline and leave accepted app idle/captureoff or recoverable baseline if required gates fail.

Evidence: FINAL_HANDOFF_RECEIPT.json certifies the immutable 35-member archive by complete independent readback. Delivery remains incomplete.
