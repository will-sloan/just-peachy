# Current readiness gate

**Protocol delivered; field app not accepted. Do not begin unsupervised field recording from the new Nemotron release yet.** F04-F20 functional blockers in FINISH_CHECKLIST must be resolved first. This document plans future consented testing; no human trial was run during finalization. Its30/60minute or1-2minute examples never override the actual release duration/storage admission.

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

Use a short repeatable task (about1-2minutes if within the release's measured duration/storage limit): speakerA alone, speakerB alone, alternating turns, a pause/return, then a brief labelled overlap. Retain spontaneous speech as a separate naturalistic run. Do not call live repetitions identical audio; record differences. A saved matched-input comparison, if later authorized, is a separate experiment and not evidence of identical live conditions.

For identity modes, test anonymous first, then compatible enrolled/open-set, selected roster and explicit closed-group assumptions separately. Gallery construction/enrollment is a distinct consented activity and does not change automatically during scoring. Do not treat assumed closed-group labels as verified recognition. Spatial contrasts need real fresh cue evidence and a placement sketch; folded front/rear ambiguity remains.

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

Record actual firmware/interface/channel map. Processed O0/O1 is not raw MIC0-MIC3. Raw+processed may be tested only after simultaneous routing is qualified; retain synchronization uncertainty, sample counts and full independent copy allocation. Four48kHz PCM16 raw channels plus16kHz processed mono are1,497,600,000bytes/hour before metadata/backups. No playback/enrollment/firmware reset is implicitly authorized by this kit.
