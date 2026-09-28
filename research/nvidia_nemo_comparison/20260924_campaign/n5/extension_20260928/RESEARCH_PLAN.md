# Nemotron on CM5: prioritized investigations

This is a research plan, not a results table. Prepared, model-free, Windows, emulated ARM64, native CM5 and held-out real-location evidence must remain separate. N1–N3 retain their scoped offline acceptance; N4/N5 remain incomplete. The disconnected Pi is not the only outstanding gate. The eight recent Windows checks cover one saved file and limited lifecycle/shadow behavior; they are not full application or real-time qualification.

The accepted N3 primary screen reported lexical WER 12.00% for A0 versus 10.21% for A2 across the two taps, with 896 reference words per tap. A0's screen used CPU and A2's used native CUDA. Separate desktop CPU component observations were approximately 0.055 compute RTF / 351 MiB sampled process RSS for A0 and 0.569 / 1025.7 MiB for A2, on their respective documented panels. These are not a matched full-stack Pi benchmark, but motivate testing both accuracy benefit and resource cost rather than automatically replacing Sherpa. See the [N3 report](../../n3/REPORT_N3.md) for all denominators, scopes and caveats.

## Composition shortlist

| ID | Composition / strategy | Question and priority |
|---|---|---|
| B00 | Existing complete Sherpa pipeline | Preserve the working baseline for accuracy, latency, CPU and memory comparisons. First control. |
| B01 | Sherpa ASR + one ordered Nemotron 3 diarizer + ReDimNet | First native candidate: can prompt captions coexist with useful speaker labels within the admitted resource budget? |
| B02 | Nemotron English ASR + the same diarizer + ReDimNet | Does any transcription benefit justify the added native compute, buffering and RAM? Paired against B01. |
| B03/B04 | B01/B02 with on-demand ReDimNet | Recompute identity only after sufficient clean speech, new/uncertain tracks or suspected change; compare calls saved, identity errors and returning speakers. Keep unknown on insufficient evidence. |
| B05/B06 | B01/B02 with external encoder bypass | Anonymous speaker-slot controls. Quantify E0 cost separately. No persistent personal-name claim or silent product replacement. |
| B07/B08 | B01/B02 captions immediately, D1 labels delayed in supported larger chunks | Trade speaker-label delay for measured throughput; keep captions independent. Compare native stream state, all-sample coverage and backlog. |
| B09 | Sherpa captions live; Nemotron ASR revision when idle or after recording; D1/E0 retained | Investigate a two-pass accuracy mode without routinely running two ASRs simultaneously. Preserve revision history and source timestamps; provisional/final text must be explicit. |
| B10 | Cheap foreground tracking between selective D1 refinements | Late research: explicit low-confidence intervals, no stale names, separate refinement state and mandatory overlap/returning-speaker checks. Not a continuously qualified diarizer. |
| B11 | Nemotron ASR + existing speaker pipeline | An ASR-only substitution control, if the actual backend can be implemented and qualified. Separates transcription gains from the effect of replacing diarization. |

B01/B02 are the primary complete-system hypotheses, not declared winners. B03–B08 are controlled changes to them. Advance only candidates on the measured accuracy/latency/resource Pareto frontier: a method must deliver a useful gain rather than simply move cost into another worker. Do not run every composition × gate × chunk × frontend × thread count. Use the existing 34-method catalogue and a small declared subset, then combine individually qualified changes.

Nemotron activity tracks are not separated audio waveforms. An overlap label does not prove that ASR transcribed both voices or assigned every word correctly. Investigate interval fusion and retrospective endpoint/segment refinement, but never invent word alignment or wait for the slow speaker lane before publishing captions. D1's in-session slots and E0's reusable voice identity serve different purposes; removing E0 is an anonymous control unless an independently validated replacement supports the needed identity behavior.

## Scheduling, compute and state

- Compare the existing caption-first threaded pipeline with separate ASR/D1 processes, measuring IPC copies, wakeups and duplicate model memory. Both share the same total admission; more processes do not create CPU capacity. Test 1-thread components first, then allocations within the admitted total, with the serial control retained.
- Keep one authoritative sample clock and one ordered D1 cache. Test native supported 1.04/0.64/0.32-second input-buffer profiles and the 30.4-second delayed/offline profile, changing the complete cache/FIFO/chunk/right-context recipe. Measure compute separately from buffering. Larger host pushes alone are not a native chunk optimization.
- Measure cold load, warm cache reuse, pause/resume, early Stop, error recovery, EOF remainder and drain. Preserve failures rather than increasing timeouts until a test passes. Cancelled epochs must not leak labels into the next session.
- Test bounded FIFO first. Recent-first recovery must declare dropped or unanalyzed source intervals and reset/reconcile state; selective uncertain-span refinement uses independent context. Track oldest pending label, queued seconds and estimated work. A bounded queue that drops speech is degraded coverage, not full real-time success.
- Only consider overlapping D1 replicas after single-stream cost and accuracy are understood; count duplicated context, identity reconciliation and RAM. Independent-session pools help throughput across sessions, not one conversation. Hold both until the hardware budget fits.
- Audit current native ARM64 kernels, compiler/ABI, thread behavior, attention implementation and existing model formats. Benchmark supported quantized variants only after export/state/tail parity and speaker-probability/DER checks. INT8/low-bit or compilation are candidates, not guaranteed Pi acceleration. Reuse local qualified artifacts; downloads or conversion beyond existing budgets remain separate decisions. No GPU or accelerator benefit is presumed.

NVIDIA's current model card recommends buffer profiles at 0.32, 0.64, 1.04 and 30.4 seconds and explicitly excludes computation from these values. Its native C++ runtime reference is a reason to inspect the existing native path; advertised GPU throughput is not a CM5 forecast. [NVIDIA model card](https://huggingface.co/nvidia/Nemotron-3-Diarization), checked September 28, 2026.

The documented streaming cache is passed from each chunk to the next, with look-ahead excluded from that chunk's scored output and special handling at EOF. This supports preserving ordered state and testing flush separately. New Transformers availability is an alternative research/reference implementation, not a requirement to install another large stack on the Pi. [Transformers implementation documentation](https://huggingface.co/docs/transformers/main/model_doc/nemotron3_diarization), checked September 28, 2026.

## Speech activity and frontends

The prior measured desktop D1/E0 collection RTF was 1.893 on its specific bank/configuration. Energy/ASR-cue speed figures in CM5_PARALLEL_DIARIZATION_FEASIBILITY_20260928.md are modeled workload estimates, not optimized inference or Pi measurements. The bank is sparse, and noisy families retain much more audio under energy gates. Do not derive deployment speed from silence savings alone.

1. Run matched ungated controls and causal shadow gates on saved audio first: exact-zero diagnostic, conservative/adaptive energy, lightweight VAD, positive ASR cues, and unions. Missing, stale or uncertain cues retain audio. No tokens does not prove silence; ASR-only exclusion remains a negative control.
2. Freeze thresholds on development material. For proposed skips, measure missed quiet/short/overlapping speech and new gate costs. Only then test actual skipping with pre-roll/hangover, reversible source-time mapping, state reset/context replay, returning speakers and flush. Zero-filling while running the model is not compute avoidance.
3. After connection, compare XVF Auto ASR versus Auto postprocessed and qualified focused outputs with fixed, logged device settings. Test whether a separate, less processed speaker-analysis feed helps E0/D1 while ASR uses the intelligibility-oriented feed. Such split feeds need measured clock/delay mapping and paired source coverage; no unqualified route switching.
4. XVF energy/activity/direction can provide positive support only after actual firmware fields and timing are verified. Beam direction is not personal identity. Preserve desired multiple nearby speakers, not just the loudest selected voice.
5. Test a real restaurant-babble condition separately from steady noise and short impacts. Use simultaneous amplified microphone reference, ASR and postprocessed taps, original chronology and paired gains. The existing synthetic captures and 0.75-second real cafeteria snippet are listening diagnostics, not this validation set.

## After the Pi is actually connected

| Order | Native investigation | Evidence needed to advance |
|---|---|---|
| H01 | Read-only hardware/software inventory | Confirm CM5/RAM, 64-bit OS, CPU flags, ABI/runtime libraries, storage, power/cooling and existing app. Decide asset subset using actual free storage; preserve original install. |
| H02 | Isolated install and saved-file smoke | Verify artifact hashes and architecture, baseline first, then D1 and each ASR alone. No microphone use needed. Missing libraries are blockers, not successful installation. |
| H03 | Native component conformance | Exact source/timestamp/state/EOF/repeat tests; resolve full-source A2 timeout and unattempted A3 separately from short-clip passes. Test E0 and punctuation/runtime/GUI prerequisites. |
| H04 | B00/B01/B02 integrated paced tests | Same saved inputs at original 1x pacing, identical total resources; capture real captions, speaker revisions, drain and full process closure. Verify GUI save/open/delete/modes/backend controls and startup failure. |
| H05 | Efficiency shortlist | One change at a time: thread/process allocation, supported chunking, on-demand E0, shadow cues, then qualified applied gates. Inspect dense-speech worst cases before adding replicas. |
| H06 | 30/60-minute endurance | CPU/RSS, clocks/temperature/throttling indicators, backlog slope/max/drain, label ages, failures and UI responsiveness. Repeated or concatenated saved clips are constructed endurance tests, not independent accuracy data. |
| H07 | Held-out real locations | Natural conversation, quiet/brief replies, overlap, returning speakers, restaurant babble, steady noise and impacts. User must be ready in the setting. Freeze settings before this evaluation; assess intelligibility and speech loss as well as noise reduction. |
| H08 | Product selection and release | Declare capability limits, choose actual measured profiles, reproduce install/rollback, finish original acceptance requirements and verify private/public packaging and Git backup. |

On reconnection the user can supply the target's existing connection details through the usual workflow. Do not probe addresses or assume a connected device from elapsed time. Do not copy Windows CPU IDs 4/14 to the Pi. Define a target admission from inventory before running numerical work; larger host or target CPU budgets are not implied by the time extension. New capture should occur when the user is physically ready; no human enrollment or training is included.

## Measurements and decisions

For each run retain source/model/code/settings hashes, exact owner identities, admission, exit and review. Accuracy: WER/CER, speaker-attributed transcription where labels exist, DER with separate false activity/miss/confusion and stated collar/overlap rules, speaker counting, short/quiet/overlap misses, returning-speaker consistency, identity errors on existing authorized references. Unlabelled audio supports latency/listening observations, not ground-truth accuracy.

Timing/resource: input release times; caption first/final latency and correction counts; initial/stable speaker-label latency; component inference time; gate, feature, IPC and context costs; wall RTF defined as processing/audio time; speech duty cycle and pause distribution; backlog slope/max/EOF drain; peak and steady RSS; actual total CPU; target clocks, temperature and throttling where available. Separate cold load from steady-state service. A responsive caption lane with indefinitely growing speaker backlog is asynchronous functionality, not sustained real-time diarization.

Compare matched compositions at fixed pacing/resources. Require no stale cross-session labels, silent fallback, hidden audio loss or ownership leaks. Retain all negative results and unattempted cells. Do not use synthetic tuning examples as independent real-world validation. Fine-tuning remains a data-suitability assessment; a future training study would require a separate authorization and genuinely separated train/validation/test data.
