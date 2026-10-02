# Concrete finish checklist

Updated 2026-10-02T08:18:23.120423+00:00. Current runtime is ready for bounded validation. Original requirements and scoped limits remain below.

## F01 — Verify the returned Pi

Status: **DONE**

Exit criterion: New boot, exact launcher/app identities, unchanged install/live/display pins, XMOS device and actual display270 recorded.

Evidence: user-reconnect-20261001-v4/RESULT.json

## F02 — Return the existing app to safe idle

Status: **DONE**

Exit criterion: One normal Stop; capture closed, hardware lease free, UI returned to Start; app and recordings preserved. ALSA1284 is a thread of app1124, not a separate source process.

Evidence: final-delivery-normal-stop-v1/RESULT.json; final-delivery-stop-completion-v1/RESULT.json

## F03 — Disable automatic listening

Status: **DONE_SAVED_SETTING_AND_TWO_IDLE_RESTARTS**

Exit criterion: Settings backup and independent restore verified; normal UI changed only auto_start_listening to false; saved hash verified. Final-release restart/boot persistence is F19.

Evidence: Candidate17 actual shortcut and autostart-command restarts preserved auto_start_listening=false/display270/captureoff. Physical coldboot remains unobserved.

## F04 — Finish the persistent local manager

Status: **DONE_BOUNDED_PERSISTENT_MANAGER_AND_RENEWAL**

Exit criterion: One persistent manual entry with current native ownership, complete local backup before another slot, independently reserved PC copies and reusable verified offload. New production policy; no consumed research launcher or expired policy as user entry.

Evidence: Actual complete candidate22 batch preserved; generic inspection/provision renewed22 to23. Current manager40612/start5055076 visible480x800, captureoff, fourunused slots.

## F05 — Issue and enforce the production recording/lifetime policy

Status: **DONE_FINITE_PRODUCTION_POLICY_AND_EXPLICIT_RENEWAL**

Exit criterion: Measure current target+PC usage; allocate finite recording count/duration, launch/recovery slots and independent backups. Show limits and exhaustion in the app. Keep CPU/RAM/disk floors, first-fault latch, capture-off startup and explicit Start; no silent cap removal or replenishment.

Evidence: Full2988319424B runtime/3307886087B install;4recordings/16launches/24h peridlelaunch;120s microphone/Chunk52,30s savedStreaming. Complete22-to23 renewal actualPASS; PowerShell wrappersyntax andPC-only planPASS. Finite owner and resource bounds remain.

## F06 — Install backend compositions with ReDimNet and TitaNet

Status: **ALL_TEN_SCOPED_NATIVE_COMPOSITIONS_PASS**

Exit criterion: Reuse the existing ReDimNet and NeMo TitaNet implementations and local assets. Expose baseline diarization and Nemotron-3 D1 with either embedding model, plus explicit anonymous operation where supported, while retaining Sherpa ONNX ASR/PnC. Pin actual encoder/runtime/frontend/mode/tap/gain manifests. Keep live Delayed and saved Streaming/Chunk52 distinct; verify each supported combination loads and runs without silent fallback. New native availability remains to be established.

Evidence: Five previous microphone passes pluscandidate16 baselineanonymous82080samples5.13s. SavedStreaming/TitaNetOff andReDimNetProcessed each131520samples8.22s wholeclosurePASScandidate16. Chunk52both8.22s candidate14, including7TitaNetqueries andnonemptyReDimNetdataactions. Noqualitybenchmark.

## F07 — Create real desktop profile shortcuts

Status: **DONE_TEN_CURRENT_SHORTCUTS_AND_ROLLBACK**

Exit criterion: Create one clearly named desktop shortcut per supported ASR/diarizer/embedding/mode combination, all selecting immutable profiles through the same versioned frontend. Each opens idle/capture off, excludes duplicate ownership and shows its actual model choices. Verify shortcut dispatch and keep baseline/rollback access.

Evidence: Candidate23 has ten exact profile shortcuts androllback.66obsolete shortcuts25411B independentlybacked/moved. Renderer8 accuratebaselineanonymous/ReDimNet-continuity label retained; previousactualduplicate exclusion andstartup passes reused.

## F08 — Complete manual Start/Stop/Return and repeated sessions

Status: **FOUR_SUCCESSIVE_NATIVE_RECORDINGS_CLOSED_PRESERVED**

Exit criterion: From the final user entry, verify New, consent, Start, Stop/drain, Save and Return; a subsequent recording gets fresh process ownership and preserves the first. Reuse old scoped component evidence; test the changed final composition once.

Evidence: Candidate8 slots01..04 used fresh processes for d1-delayed, baseline-titanet, baseline and d1-anonymous. Workflow7 verified all prior complete source/local-copy memberships and hashes before and after each subsequent operation. All source/controller/model owners closed before the next local backup/slot.

## F09 — Finish failure recovery

Status: **CANCEL_BEFORE_RECORDING_AND_EARLY_CLOSE_RECOVERY_PASS**

Exit criterion: Verify missing/corrupt backend asset, startup failure and one interrupted/failed session in the final manager. Stop before diagnostics, release actual source/model/writers, preserve partial data, fence unresolved owners and provide a usable recovery/rollback path without resetting old failed ledgers.

Evidence: Candidate16slot4CLOSED_UNUSED_BROKER preserves fullallocation without child/source/model. Candidate16earlyClose triggeredactualautomaticrollback, allfivecompletePCtreesretained. Manager9fix actualcandidate17earlyClose/naturalexit/autostartreopenPASS. No arbitrarypowerlossclaim.

## F10 — Finish the480x800 UI and nonempty captions

Status: **NATIVE_NONEMPTY_CAPTION_REOPEN_PASS_PHYSICAL_TOUCH_OPEN**

Exit criterion: All required controls reachable with270orientation; correct backend/mode, recording state and unavailable reasons visible. Use an existing authorized saved speech input for actual nonempty captions/audio links, Pending/Unknown and independent caption timing. No audible playback or solicited speech.

Evidence: Candidate14 slot3 real saved-transcript UI showed one nonempty caption/audio-link control after exact import and explicit Reopen,480x800/270. No playback, physical touch or accuracy claim.

## F11 — Verify saved history and data actions in the final release

Status: **NATIVE_CROSS_SESSION_HISTORY_AND_SCOPED_DATA_ACTIONS_PASS**

Exit criterion: Save/reopen two recordings, select earlier history, export/import and delete only a verified disposable copy after backup. Preserve complete audio/events/probabilities/timestamps. Existing V123/V128 passes are reused; rerun only final-entry integration or changed nonempty-content gaps.

Evidence: Manager11 exposes13 closed sessions. Candidate18 actual AudioOff/nonempty history passed before legacy rejection; candidate19 legacy Processed/nonempty caption Open/Back passed, no capture/model/recording slot consumed. Original pinned legacy journal method fixes six-versus-seven source-pin schema, without changing old receipts. Earlier actual Save/export/readback/disposableDelete/Import/Reopen evidence retained.

## F12 — Verify personal gallery compatibility

Status: **SEPARATE_ENCODERS_ACTUALLY_QUERY_GALLERY_QUALITY_OPEN**

Exit criterion: Read-only review of UUID/encoder/revision/tap/gain namespaces, including separate ReDimNet and TitaNet galleries. Reuse existing TitaNet namespace support; never compare or relabel vectors across models, silently enroll, migrate or overwrite personal data. Compatible references load; incompatible/empty galleries remain Unknown with a clear explanation. Preserve schema rollback.

Evidence: Candidate14 TitaNet completed seven real saved-speech embedding queries using its original frontend/weights, without raising768MiB AS. E0 separate gallery remains preserved; TitaNet gallery remains separately empty/Unknown. No enrollment, model-space conversion or recognition-quality claim.

## F13 — Add optional processed recording controls

Status: **OFF_AND_PROCESSED_NATIVE_COMPLETE_PASS**

Exit criterion: Provide Off/Processed selection before Start, recording indicator, elapsed time, admitted remaining duration/storage and Stop. Save exact model-input audio losslessly with its rate, channels, tap, gain and resampling metadata.

Evidence: Candidate16StreamingTitaNetAudioOff consumes131520samples without storedaudio and closescleanly. StreamingReDimNetProcessed preserves131520float/WAVsamples/completeevents. Fullreservationretained forOff.

## F14 — Resolve true raw microphone support

Status: **NATIVE_FOUR_MIC_RAW_AND_PROCESSED_RECORDING_PASS**

Exit criterion: Check actual firmware/routing for simultaneous physical MIC0-MIC3 and processed taps. If supported, qualify one bounded paired recording with synchronized clocks, sample counts and route restoration. If unsupported, visibly disable Raw+processed with the exact reason; never relabel O0/O1 or float/WAV as raw microphones.

Evidence: Candidate22 actual UI raw consent/Start/Stop/Save/Return produced85919 paired samples5.3699375s. PhysicalMIC0-MIC3 signedPCM32/16kHz from firmware category1 packed I2S48kHz, zero marker errors; exact processed model-input count. No48kHzADC/equal acoustic latency claim. All routes restored/captureclosed/leasesfree. Whole203file4872052B original and independent local backup copied/readback onPC, identicalmanifest0c2d958f8ed9051589e5432166736fa585b94dc95a0a63173aa19baa02cb6785.

## F15 — Close recording integrity and storage accounting

Status: **RAW_PROCESSED_COUNTS_CLOSURE_AND_FULL_COPIES_PASS**

Exit criterion: Bound every writer and count raw/processed/events/metadata plus independent local and PC copies. Enforce at least5GiB Pi/C50GiB/G75GiB free floors, finite duration, no drop/overflow masquerading as success, complete Stop/closed files and final manifest hashes. Preserve partial failures and originals.

Evidence: Candidate22 raw1374704B/f32le343676B/WAV171882B each85919samples. D1closed537frames; source537blocks/257757transportframes/no drops/fault. Source/controller/archive/writers closed. One transport prefix/two incomplete terminal frames explicitly recorded; all complete packed samples retained. Full independent raw allocation unchanged.

## F16 — Deliver verified copy-to-PC offload

Status: **REUSABLE_RAW_AND_PROCESSED_PC_OFFLOAD_PASS**

Exit criterion: A reusable documented export command/control copies a stopped recording into a fresh private PC destination. Verify membership, sizes, SHA256 and full readback; retain receipt and path. Preserve interrupted transfers and Pi originals; no automatic deletion.

Evidence: export_runtime_recording_v4 copied source and Pi-local backup independently:203files4872052B425measuredchunks27dirs each, matchingmanifest0c2d958f8ed9051589e5432166736fa585b94dc95a0a63173aa19baa02cb6785. No deletion. Both exact native exporters closed, manager idle.

## F17 — Finish deterministic install and health checks

Status: **DONE_PREPARED_CM5_DEPLOYMENT_AND_INDEPENDENT_KIT_RESTORE**

Exit criterion: Versioned code/config/runtime manifests; all pinned assets already local; native aarch64/runtime/dependency identity verified. Health reports missing assets, incompatible gallery, disk limits or unavailable hardware explicitly and never downloads on first use.

Evidence: field-runtime-v23-install and runtime-delivery-v23/BACKUP.json:2586members91554957B, independent ZIP and expanded restore

## F18 — Verify activation, rollback and local recovery

Status: **DONE_SCOPED_LOCAL_ROLLBACK_AND_REACTIVATION**

Exit criterion: Back up active code/config/desktop/autostart manifests with independent restore readback. Activate final candidate, exercise rollback and restore candidate. Prove recovery works locally before denying its network access; preserve baseline and personal data.

Evidence: Candidate22 normalClose/exactdeath/fullPCpreservation/pinnedrollback restored idlebaseline. Fresh23 activation passed. Priorautomaticrollback/normalstartup-commandrestart retained; no powerlossclaim.

## F19 — Verify final startup and offline operation

Status: **DONE_SOFTWARE_OFFLINE_AND_STARTUP_PHYSICAL_TESTS_PLANNED**

Exit criterion: Final shortcut and one final-release restart/coldboot open idle with270orientation and no automatic listening. Exercise its supported operation with external network unavailable after local recovery is proven. Distinguish software network denial from physically unplugged testing.

Evidence: Actualbroker/childInternet socketdenial andcandidate22 offline rawrecordingpassed. Current23 samecode/idle480x800/display270. Earlieractualshortcut/autostart-commandrestart passed. Cable-disconnectedcoldboot/touch remain operator validation.

## F20 — Run one bounded final recording/resource acceptance

Status: **FINAL_RAW_OFFLINE_COMPOSITION_AND_PAIRED_PC_BACKUPS_PASS**

Exit criterion: Use the final installed composition for its supported bounded recording duration, then Stop/Save/PCcopy. Record combined resource/CPU/available-memory/disk observations, complete samples/events and actual cleanup. Reuse this same run for F08,F13,F15,F16 where it supplies evidence; no independent duplicate healthy runs. Use only focused functional checks for the newly added TitaNet routes, reusing prior healthy evidence; do not add an embedding-quality benchmark campaign.

Evidence: Candidate22 changed raw+processed D1Delayed/TitaNet composition ran85919samples. Actual child IPv4/IPv6socketdenial/seccomp retained, fullsource/model/UIStop/Save/Return and both independentPCcopies complete. Quietfunctionalcheck, no newquality/noisyhuman/physicaltouch evidence. Unchanged ten model-route passes reused.

## F21 — Declare camera, IMU and physical-control capabilities

Status: **DONE_ACTUAL_AUDIO_DISPLAY_OTHER_CAPABILITIES_DECLARED**

Exit criterion: Retain one actual hardware profile and exact known routes/pins; keep unknown GPIO disabled. Show optional/on-demand camera and IMU availability honestly, with axes/clock/motion limits. No invented pin mapping or unmeasured physical-touch/button pass.

Evidence: ActualfourMIC16kHz raw/processed route qualified/restored;display270. Camera/IMU/unknownGPIO explicitlyunqualified. No physicaltouch/powercycle claim.

## F22 — Freeze versioned artifacts and reconcile all original requirements

Status: **DONE_RECONCILED_WITH_GAPS**

Exit criterion: Map every retained Windows/Pi composition to its actual source/config/runtime/model hashes and Git ref. Reconcile N1-N5, all34methods and full240-cell N4 denominator with existing receipts. Mark unrun/failed/deferred entries explicitly; no new campaign or benchmark sweep to fill them.

Evidence: FINAL_COVERAGE.md; original N5,73notes,240scene/panel denominators and all34methods retained; FINAL_ARTIFACT_INDEX.json.

## F23 — Finish the operator documentation

Status: **DONE_CURRENT_OPERATOR_GUIDES**

Exit criterion: Exact Start Here, named shortcuts, shared Mode/Backend guides, recording/offload instructions, Enrollment Compatibility, Install/Health, Update/Rollback, Licence Ledger, hardware template, paths/backups and troubleshooting. Include PowerShell/CMD/Anaconda commands for every new code path and supported limits/latency. Include a complete supported-combination table for ReDimNet versus TitaNet, exact shortcut names and commands, input modes, model/gallery compatibility, limits and unavailable reasons.

Evidence: Current ten-profile commands, formats, galleries, limits, offload4, renewal, recovery, paths and physical/noisy validation scope

## F24 — Finish the noisy-environment testing kit

Status: **DONE_PROTOCOL_ONLY**

Exit criterion: Consent/privacy instructions, test scenes, reference/ground-truth method, timing/sample/route metadata, expected controls, naming/Unknown/overlap checks, failure rubric and run/results template. Actual noisy-human quality and physical-touch observations remain future measurements until performed.

Evidence: FIELD_VALIDATION.md/FIELD_RUN_TEMPLATE.json; no human/physical/noise-quality result.

## F25 — Create and verify the final private and Git backups

Status: **PRIVATE_CODE_DATA_KIT_RESTORE_PASS_GIT_PUBLICATION_PENDING**

Exit criterion: Final deployable release/config and private recordings have complete independent copies/hash/readback and a demonstrated restore path. Push only reviewed small source/manifests/redacted reports; verify remote branch/profile refs. Never publish audio, profiles, vectors, credentials or model weights.

Evidence: Current source/active configuration independent restores, complete raw and whole batch copies, full prepared-device kit restore

## F26 — Build the final handoff and leave a safe device

Status: **DOCUMENTS_FROZEN_FINAL_EXTERNAL_RECEIPTS_PENDING**

Exit criterion: Condensed ChatGPT ZIP<=20MiB(target<=10), WORKBOOK_UPDATE and artifact/hash index; deployable assets separately. Update ACCEPTANCE with actual evidence and all remaining blockers; close owned research, pause automation by deadline and leave accepted app idle/captureoff or recoverable baseline if required gates fail.

Evidence: Final package/Git/automation outcome is recorded by FINAL_HANDOFF_RECEIPT.json and FINALIZATION_RECEIPT.json after the immutable documentation ZIP is built

