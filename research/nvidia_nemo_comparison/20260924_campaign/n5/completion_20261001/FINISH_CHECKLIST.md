# Concrete final delivery checklist

Delivery is **INCOMPLETE**. Hard deadline2026-10-01T16:14:58Z; feature freeze15:14:58Z. F01/F02 completed; F04 gained scoped native integration but its persistent manual entry is missing. F22-F26 finalization does not waive required runtime gates.

## F01 — Verify the returned Pi

Status: **DONE**.

Done means: New boot, exact launcher/app identities, unchanged install/live/display pins, XMOS device and actual display270 recorded.

Evidence/scope: user-reconnect-20261001-v4/RESULT.json

## F02 — Return the existing app to safe idle

Status: **DONE**.

Done means: One normal Stop; capture closed, hardware lease free, UI returned to Start; app and recordings preserved. ALSA1284 is a thread of app1124, not a separate source process.

Evidence/scope: final-delivery-normal-stop-v1/RESULT.json; final-delivery-stop-completion-v1/RESULT.json

## F03 — Disable automatic listening

Status: **SAVED_NOT_REBOOT_TESTED**.

Done means: Settings backup and independent restore verified; normal UI changed only auto_start_listening to false; saved hash verified. Final-release restart/boot persistence is F19.

Evidence/scope: final-delivery-idle-start-v2/RESULT.json

## F04 — Finish the persistent local manager

Status: **PARTIAL_NATIVE_INTEGRATION_PASS_MANUAL_ENTRY_OPEN**.

Done means: Wire the prepared initializer, broker, finish/reopen, census/export receiver and exact owner closure into one local manual entry. Bind current boot/PID identities, preserve full617760944-byte qualification reservation, and require complete local/PC copies before another slot. No consumed research launcher or expired policy as a user entry.

Evidence/scope: CHECK_SUMMARY_V141; native reserve/run/finish/localbackup/reopen plus separate full PC copies. Persistent manual entry remains missing.

## F05 — Issue and enforce the production recording/lifetime policy

Status: **OPEN**.

Done means: Measure current target+PC usage; allocate finite recording count/duration, launch/recovery slots and independent backups. Show limits and exhaustion in the app. Keep CPU/RAM/disk floors, first-fault latch, capture-off startup and explicit Start; no silent cap removal or replenishment.

## F06 — Install the selected backend compositions

Status: **OPEN**.

Done means: One frontend with baseline, Sherpa ONNX/PnC+Nemotron-3 D1+compatible ReDimNet, and an explicit anonymous choice where supported. Pin actual executed model/runtime/buffer/gain/tap manifests. Keep live Delayed and saved Streaming/Chunk52 availability distinct; unavailable choices explain why and never silently fall back.

## F07 — Create real desktop profile shortcuts

Status: **OPEN**.

Done means: Named Pi desktop entries select those manifests through the same versioned manager, start idle and exclude duplicate app/microphone/model owners. Verify each retained shortcut's actual launch; retain baseline/rollback entry.

## F08 — Complete manual Start/Stop/Return and repeated sessions

Status: **OPEN**.

Done means: From the final user entry, verify New, consent, Start, Stop/drain, Save and Return; a subsequent recording gets fresh process ownership and preserves the first. Reuse old scoped component evidence; test the changed final composition once.

## F09 — Finish failure recovery

Status: **OPEN**.

Done means: Verify missing/corrupt backend asset, startup failure and one interrupted/failed session in the final manager. Stop before diagnostics, release actual source/model/writers, preserve partial data, fence unresolved owners and provide a usable recovery/rollback path without resetting old failed ledgers.

## F10 — Finish the480x800 UI and nonempty captions

Status: **OPEN**.

Done means: All required controls reachable with270orientation; correct backend/mode, recording state and unavailable reasons visible. Use an existing authorized saved speech input for actual nonempty captions/audio links, Pending/Unknown and independent caption timing. No audible playback or solicited speech.

## F11 — Verify saved history and data actions in the final release

Status: **OPEN**.

Done means: Save/reopen two recordings, select earlier history, export/import and delete only a verified disposable copy after backup. Preserve complete audio/events/probabilities/timestamps. Existing V123/V128 passes are reused; rerun only final-entry integration or changed nonempty-content gaps.

## F12 — Verify personal gallery compatibility

Status: **OPEN**.

Done means: Read-only review of UUID/encoder/revision/tap/gain namespaces and schema migration/rollback compatibility. Compatible references load; incompatible/empty galleries clearly stay Unknown. Preserve profiles/photos/vectors; no enrollment or reinterpretation of old vectors.

## F13 — Add optional processed recording controls

Status: **OPEN**.

Done means: Provide Off/Processed selection before Start, recording indicator, elapsed time, admitted remaining duration/storage and Stop. Save exact model-input audio losslessly with its rate, channels, tap, gain and resampling metadata.

## F14 — Resolve true raw microphone support

Status: **OPEN_CONDITIONAL_HARDWARE_CAPABILITY**.

Done means: Check actual firmware/routing for simultaneous physical MIC0-MIC3 and processed taps. If supported, qualify one bounded paired recording with synchronized clocks, sample counts and route restoration. If unsupported, visibly disable Raw+processed with the exact reason; never relabel O0/O1 or float/WAV as raw microphones.

Evidence/scope: V141 actual firmware3.2.1/4reported mics/8channel endpoint/O0processed route; simultaneous rawMIC0-MIC3 NOT_QUALIFIED, unsupported hardware not proven.

## F15 — Close recording integrity and storage accounting

Status: **OPEN**.

Done means: Bound every writer and count raw/processed/events/metadata plus independent local and PC copies. Enforce at least5GiB Pi/C50GiB/G75GiB free floors, finite duration, no drop/overflow masquerading as success, complete Stop/closed files and final manifest hashes. Preserve partial failures and originals.

## F16 — Deliver verified copy-to-PC offload

Status: **OPEN**.

Done means: A reusable documented export command/control copies a stopped recording into a fresh private PC destination. Verify membership, sizes, SHA256 and full readback; retain receipt and path. Preserve interrupted transfers and Pi originals; no automatic deletion.

Evidence/scope: V141 complete private broker and independent manager copies passed; reusable production operator offload flow remains OPEN.

## F17 — Finish deterministic install and health checks

Status: **OPEN**.

Done means: Versioned code/config/runtime manifests; all pinned assets already local; native aarch64/runtime/dependency identity verified. Health reports missing assets, incompatible gallery, disk limits or unavailable hardware explicitly and never downloads on first use.

## F18 — Verify activation, rollback and local recovery

Status: **OPEN**.

Done means: Back up active code/config/desktop/autostart manifests with independent restore readback. Activate final candidate, exercise rollback and restore candidate. Prove recovery works locally before denying its network access; preserve baseline and personal data.

## F19 — Verify final startup and offline operation

Status: **OPEN**.

Done means: Final shortcut and one final-release restart/coldboot open idle with270orientation and no automatic listening. Exercise its supported operation with external network unavailable after local recovery is proven. Distinguish software network denial from physically unplugged testing.

## F20 — Run one bounded final recording/resource acceptance

Status: **OPEN**.

Done means: Use the final installed composition for its supported bounded recording duration, then Stop/Save/PCcopy. Record combined resource/CPU/available-memory/disk observations, complete samples/events and actual cleanup. Reuse this same run for F08,F13,F15,F16 where it supplies evidence; no independent duplicate healthy runs.

## F21 — Declare camera, IMU and physical-control capabilities

Status: **DONE_CAPABILITY_DECLARATION_PHYSICAL_TESTS_OPEN**.

Done means: Retain one actual hardware profile and exact known routes/pins; keep unknown GPIO disabled. Show optional/on-demand camera and IMU availability honestly, with axes/clock/motion limits. No invented pin mapping or unmeasured physical-touch/button pass.

Evidence/scope: HARDWARE_CAPABILITIES.json; actual audio/display, explicit unqualified camera/IMU/buttons/raw.

## F22 — Freeze versioned artifacts and reconcile all original requirements

Status: **DONE_RECONCILED_WITH_GAPS**.

Done means: Map every retained Windows/Pi composition to its actual source/config/runtime/model hashes and Git ref. Reconcile N1-N5, all34methods and full240-cell N4 denominator with existing receipts. Mark unrun/failed/deferred entries explicitly; no new campaign or benchmark sweep to fill them.

Evidence/scope: FINAL_COVERAGE.md; original N5,73notes,240scene/panel denominators and all34methods retained; FINAL_ARTIFACT_INDEX.json.

## F23 — Finish the operator documentation

Status: **FINALIZING_CURRENT_STATE_DOCUMENTATION**.

Done means: Exact Start Here, named shortcuts, shared Mode/Backend guides, recording/offload instructions, Enrollment Compatibility, Install/Health, Update/Rollback, Licence Ledger, hardware template, paths/backups and troubleshooting. Include PowerShell/CMD/Anaconda commands for every new code path and supported limits/latency.

Evidence/scope: START_HERE,FINAL_OPERATOR_GUIDE,MODE_GUIDE,PATHS; missing runtime workflows explicitly unavailable.

## F24 — Finish the noisy-environment testing kit

Status: **DONE_PROTOCOL_ONLY**.

Done means: Consent/privacy instructions, test scenes, reference/ground-truth method, timing/sample/route metadata, expected controls, naming/Unknown/overlap checks, failure rubric and run/results template. Actual noisy-human quality and physical-touch observations remain future measurements until performed.

Evidence/scope: FIELD_VALIDATION.md/FIELD_RUN_TEMPLATE.json; no human/physical/noise-quality result.

## F25 — Create and verify the final private and Git backups

Status: **PARTIAL_RESEARCH_BACKUPS_VERIFIED_FINAL_PUBLICATION_PENDING**.

Done means: Final deployable release/config and private recordings have complete independent copies/hash/readback and a demonstrated restore path. Push only reviewed small source/manifests/redacted reports; verify remote branch/profile refs. Never publish audio, profiles, vectors, credentials or model weights.

Evidence/scope: 24newsource files196438B exactbackups+independentrestores; both PCtrees exactreadback; no finalproductionrelease torestore.

## F26 — Build the final handoff and leave a safe device

Status: **FINALIZING_INCOMPLETE_DELIVERY**.

Done means: Condensed ChatGPT ZIP<=20MiB(target<=10), WORKBOOK_UPDATE and artifact/hash index; deployable assets separately. Update ACCEPTANCE with actual evidence and all remaining blockers; close owned research, pause automation by deadline and leave accepted app idle/captureoff or recoverable baseline if required gates fail.

## Execution rule

Each action must close a named missing criterion. Reuse unchanged healthy evidence; no generic sweeps, new campaigns, deadline extension or consumed root/policy reuse. Feature/model work is frozen. Missing required functionality stays OPEN. Future continuation requires new explicit authority.
