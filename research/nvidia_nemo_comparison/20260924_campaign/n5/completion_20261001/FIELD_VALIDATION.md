# Current validation scope

Build21 separates backend, embedding, application Mode and live/saved source.
Normal Live uses manual Stop with storage/resource guards and capacity-driven
UUID recordings; controlled developer replay retains explicit finite policies.
See CURRENT_RUNTIME_PROGRESS and MODE_GUIDE for exact qualification.
A live input route is not a sustainable-real-time claim. Preserve v27 as rollback.
# In-person noisy-environment validation framework

Purpose: compare the frozen, accepted offline modes in real settings after delivery. This is a future operator protocol, not a claim that new speech/noise accuracy has been measured. Use only actually enabled combinations from the final mode guide. Keep recordings and speaker/profile information private; use consenting test participants and anonymous run aliases.

## Prepare once

Record release/commit, full backend and D1 geometry, model/runtime hashes, source tap/gain/preprocessing, enabled recipe, roster policy and compatible gallery version. Freeze these during comparisons. Record device orientation, placement, distance, power source and available storage. Verify offline startup, touch, Stop, Save and Reopen using OFFLINE_ACCEPTANCE. Keep an exact backup before travel. Do not assume battery endurance or sensor availability unless measured.

Copy FIELD_RUN_TEMPLATE.json into private run storage; assign unique run and location aliases. Keep names/actual venue details out of shared summaries. Use a fresh process/session when changing D1 runtime and verify the previous worker is closed. Do not launch an unavailable experimental method merely because it appears in the research catalogue.

## Practical sequence

| Phase | Suggested setting/task | What to inspect |
|---|---|---|
| Quiet reference | Same participants and placement, single speaker then ordinary turn-taking | First-caption/first-label delay, missed words, Unknown behavior, basic source integrity |
| Steady noise | Fan/ventilation or comparable continuous background | Low-level speech, stable labels, sustained queue growth |
| Competing voices | Consented conversation with cafe-like babble around it | Wrong-person labels, outsider rejection, delayed association, split/merged anonymous tracks |
| Reverberation/transients | Reflective room or intermittent nearby sounds | False activity, recovery after a transient, continuity and caption retention |
| Movement/return | A speaker pauses, returns or changes position; overlap only in a labelled planned segment | Returning-speaker identity, stale spatial cues, overlap ambiguity, recovery after movement |

Start with one functional pilot at each setting. Compare two delivery-qualified D1 choices on the same participant task and placement, counterbalancing order (A/B then B/A) to reduce warmup/order confounding. Add the third choice only when there is a concrete unresolved tradeoff. This is a targeted test, not all product modes x backends x every noise condition.

Use a short repeatable task (about1-2minutes if within the release's measured duration/storage limit): speakerA alone, speakerB alone, alternating turns, a pause/return, then a brief labelled overlap. Retain spontaneous speech as a separate naturalistic run. Do not call live repetitions identical audio; record differences. A saved matched-input comparison is a separate experiment and not evidence of identical live conditions. The operator's planned workflow below is deferred; no batch runner is being implemented now.

For identity modes, test anonymous first, then compatible enrolled/open-set, selected roster and explicit closed-group assumptions separately. Gallery construction/enrollment is a distinct consented activity and does not change automatically during scoring. Do not treat assumed closed-group labels as verified recognition. Spatial contrasts need real fresh cue evidence and a placement sketch; folded front/rear ambiguity remains.

## Planned representative recording and matched Pi replay

The preferred future comparison workflow is one consented dinner-table or noisy-setting conversation with the device stationary. Enroll the participating people separately with ReDimNet and TitaNet, then freeze both model-specific galleries before the evaluation conversation. Enrollment audio should be separate from scored conversation audio. Keep anonymous participant aliases and a seating sketch alongside the actual application Mode and selected roster.

After Stop and drain, retain a complete private session: exact processed replay audio, qualified physical raw channels when available, source sample clocks, full captions/revisions, beam and BMI270 timelines, source routing/gain, backend/Mode settings, model hashes, and the exact gallery snapshot or hash-bound private copies. Saving audio alone does not preserve the enrollment or spatial evidence used by the live session.

A future Windows coordinator can connect to the Pi and run compatible backend, embedding and application Mode combinations sequentially on that same session. Each run should use fresh model state and its own result directory while preserving the original recording and frozen galleries. Record unsupported combinations explicitly rather than silently substituting a backend. The models should execute on the Pi when measuring Pi performance.

Keep two replay measurements separate: unpaced replay for processing cost, and source-clock-paced replay for caption/speaker presentation timing. A timed screen recording can show first output, revisions and backlog alongside machine-readable events. Measure screen-capture overhead or use an external camera for an undisturbed display measurement; an accelerated replay video is not a live-latency result. Copy complete private results and selected screen recordings to Windows with manifest/hash readback, retaining the Pi originals by default.

Backend comparisons using identical processed audio are repeatable. They do not compare different XVF acquisition or beam-processing routes: an already processed waveform cannot recreate a different hardware route. Such comparisons need an appropriate raw reprocessing implementation or separately qualified simultaneous taps. Replay of spatial Modes must consume the recorded beam/motion timeline and seating context; current tablet sensors must not influence historical audio. That synchronized spatial replay integration remains future work.

Reference words and time-aligned speaker/overlap labels are needed for accuracy scores. Without them, report functionality, timing, resource behavior and qualitative observations. Hold out separate conversations before tuning thresholds or choosing a winning configuration. Retain a smaller live test of the selected configurations afterward, because matched replay alone does not qualify microphone acquisition, real-world responsiveness, motion behavior or battery endurance.

This section records the proposed workflow only. Batch orchestration, automated screen recording, gallery transport and synchronized spatial replay are not claimed implemented or accepted.

## During each run

1. Confirm exact mode/backend, new session, Ethernet disconnected/network state, current source tap and free space. Leave display filters off for primary comparisons.
2. Start once. Note first caption and first provisional/stable speaker label separately. Let the chosen buffering delay elapse; blank early labels are not immediate proof of a failure.
3. Mark approximate task events using the displayed/source clock. Log speaker changes, overlap, movement, quiet speech and unexpected background events without changing settings mid-run.
4. Observe captions retained, anonymous split/merge, incorrect name versus Unknown, returning-speaker recovery, backlog and thermal/resource alerts. No words is not evidence of silence.
5. Stop and wait for drain/closure. Save, reopen, verify duration/sample/word-history continuity and the exact selected mode in metadata. Record gaps/faults even when the GUI looks normal.
6. Hash/copy the complete private run folder and verify the copy before leaving. Keep the original and failure data. Record a clean next-process launch only when needed for the next mode.

If the app reports a source fault, failed archive, ownership still held or an enforced resource limit, stop that trial and preserve its logs. Do not repeatedly press Start or reset firmware to hide the failure. Resume only through the documented recovery path. An interrupted run remains interrupted.

## Separate functional and quality conclusions

Functional acceptance records source/sample/time integrity, start/stop/closure, complete storage/reopen and controls. Resource acceptance records wall/CPU time, sampled peakRSS/availableRAM, temperature, clock/throttle, queue/backlog and drain. Record whether measurements were sampled and whether another app was running.

Quality evaluation needs independently prepared reference words and speaker/time annotations from the actual consenting session. Freeze transcription/overlap/collar/scoring policies before calculating WER/DER or identity error. Keep raw and formatted text separate; report wrong-name, Unknown and assumed-label outcomes separately. Unannotated field notes are useful observations, not benchmark scores. Report per-condition/per-run results and failures; do not generalize from one cafe session.

Reserve held-out conversations/locations for a final frozen-mode check. If settings are tuned using a trial, label it development data and do not reuse it as untouched validation. The final report should state enabled release, cases actually run, missing conditions, latency/resource tradeoffs and next targeted change.

## Operator deliverables after a visit

One private folder per run, completed template, retained media/journals/telemetry/faults, reference annotations when available, and an exact backup manifest. Shared summary contains anonymous run IDs, release/mode, observed outcomes and explicit limitations. Never upload private audio, transcripts, profiles or vectors to the code repository.

## Fixed failure rubric

- Integrity failure: any missing accepted audio/event, unreported drop, broken clock/manifest, incomplete Stop/closure or unverified copy. Preserve the failed run; do not score it as complete.
- Functional failure: wrong backend, silent fallback, unavailable control, frozen UI, unknown owner or unrecoverable startup. Keep the original error and exact attempted action.
- Quality observation: missed/inserted words, wrong name, excessive Unknown, anonymous split/merge, overlap error. Requires independent reference before a numerical score; it is not an integrity pass/fail substitute.
- Resource failure: admitted duration/storage/available-memory/queue limit breached, sustained backlog or forced termination. Report actual sampled values and missing intervals.

Record actual firmware/interface/channel map. Processed O0/O1 is not raw MIC0-MIC3. The qualified v29 physical route is four16kHz PCM32 channels packed over48kHz stereoS32, paired with exact16kHz model-input audio. It is not four48kHz microphone channels. Preserve channel order, sample indexes, synchronization metadata and complete copy allocation; use the actual StoragePolicy reservation for every run. No playback/enrollment/firmware reset is implicitly authorized by this kit.

## Mounted-motion validation addition

Use MOTION_GUIDE and record results in the template's `motion` fields. These are
future physical observations, not extra checks already performed or automatic jobs.

1. Leave the device quiet briefly and observe automatic reference acquisition.
2. With a stationary consented speaker, rotate and tilt the tablet. Raw beam arrows
   must follow microphone-relative direction; trusted location association should
   use the relative reference without changing the voice embedding itself.
3. Move the tablet sideways. Observe motion/trust invalidation; do not expect a
   reliable room trajectory or speaker range from accelerometer integration.
4. Toggle the optional orientation graphic and tap it. Only the graphic zero should
   change. After gaps/movement, observe reacquisition rather than guessed angles.
5. Compare ReDimNet/TitaNet with separately compatible galleries and matched input.
   A plain saved WAV must not react to present-day tablet rotation. Record drift,
   false movement indications and battery/temperature over separately admitted runs.

Keep normal duration, resource and storage limits. There is no four-recording global counter in v29. Long-term drift/endurance needs its own
bounded plan; this protocol does not enlarge the current runtime allowance.
