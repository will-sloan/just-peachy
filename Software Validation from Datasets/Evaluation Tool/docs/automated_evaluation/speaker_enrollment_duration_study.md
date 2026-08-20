# Scientific speaker enrollment and live-identification duration study

## Scientific questions

This additive study begins only after finalist speaker-embedding backends have been selected. It asks how many independent enrollment utterances and how much enrollment audio a user should provide, how those embeddings should be represented, how much accumulating live audio is needed for known identification and safe Unknown rejection, and whether greater enrollment burden reduces live recognition delay.

The backend is a selected architecture, not the main independent variable. When two finalists remain, both receive the identical frozen cohort, source slices, phase definitions, and held-out probes. Embeddings, representations, calibration scores, and thresholds remain backend-specific.

## Source and feasibility boundary

The default source is the validated Common Voice English 60+ breadth protocol, supplied explicitly with `-SourceProtocolRoot`. Its age categories and optional gender/accent fields are self-reported metadata. Its speech is prompted/read, not conversational. It does not provide reliable session, microphone, or device identities.

The frozen upstream split gives every known speaker five enrollment, ten calibration, and fifteen evaluation clips. The v1 audit found that 243 of 272 known speakers have at least 20 seconds across the five enrollment clips. Requiring three independent calibration and three independent evaluation parent clips of at least five seconds leaves a paired core of 221 known speakers. The same rule retains 47 calibration Unknown and 92 evaluation Unknown speakers.

No known speaker supports an optional ten-second nested probe under the combined 20-second enrollment and three-ten-second-probes-per-partition requirements (19 have at least one 10-second calibration clip, 39 have at least one 10-second evaluation clip, but none has three in both partitions). It is therefore retained in the audit but excluded from the primary v1 grid. This is an explicit design adjustment, not a silent omission.

## Paired cohort and source separation

All primary configurations use the same 221 known identities and the same three parent calibration plus three parent evaluation recordings per known speaker. Unknown speakers are never enrolled. Calibration Unknown and evaluation Unknown identities remain disjoint. Enrollment, calibration, and evaluation parent item IDs are mutually source-disjoint for each known speaker.

The upstream selection already enforces unique within-speaker transcripts. Transcript hashes remain in the study manifests so lexical overlap can be diagnosed. Multi-utterance enrollment uses distinct source phrases. No session diversity is inferred from filenames.

## Study phases

### A — EnrollmentCount

Natural complete enrollment utterances are tested at N=1, 2, 3, and 5 with normalized-mean aggregation and natural full probe parents. Five deterministic cyclic enrollment-selection repetitions measure sensitivity to exact enrollment examples. Because the upstream split contains exactly five enrollment clips, all N=5 repetitions contain the same complete set; they are not treated as five independent evidence sets.

### B — EnrollmentDuration

Available audio budgets of 1, 2, 5, 10, and 20 seconds are constructed by deterministically accumulating independent enrollment clips and trimming only the final clip to the exact remaining budget. Audio is never repeated or padded. These are waveform/audio durations, not claimed voiced-speech durations.

### C — Aggregation

At matched natural N=2, 3, and 5 enrollment selections, the study compares:

- `normalized_mean`: L2-normalize exemplars, average, then L2-normalize the centroid;
- `duration_weighted_mean`: weight normalized exemplars by supplied audio duration before final normalization;
- `multi_template_mean_score`: keep each normalized exemplar and average its probe cosine scores.

N=1 is not used for the aggregation comparison because the methods are effectively uninformative there.

### D — ProbeDuration

One explicit completed enrollment configuration selected after Phases A-C is held fixed. Each parent probe creates nested prefixes at 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, and 5.00 seconds from a common zero-second file start. The crop policy is model-independent and versioned as `available-audio-prefix.v1`. Backends may reject short slices; no padding is allowed, and `TECHNICALLY_INVALID` is distinct from an inaccurate valid result.

### E — JointFrontier

Phase E requires an external `speaker-enrollment-joint-decision.v1` YAML file selecting a small number of observed enrollment points and observed probe durations. The tool will not preselect the illustrative 2/5/10-second by 0.75/1.5/3-second grid. This prevents an unreviewed Cartesian product and keeps product gates outside scientific measurement.

## Immutable slices and cache

Every slice ID hashes its parent source item, crop start and end in microseconds, and duration-policy version. Probe variants retain a shared `parent_item_id`. The backend cache additionally binds the slice to source-audio SHA-256, backend/model/config identity, preprocessing identity, study config, and Git code identity. One slice/backend embedding is extracted once and reused across aggregation and scoring configurations.

Changing an aggregation method does not re-extract audio. Changing a result-affecting crop, source bytes, backend asset/config, preprocessing contract, policy, or code identity produces a different cache identity. Failed and too-short observations are cached as explicit outcomes.

## Calibration, evaluation, and Unknown handling

Every backend/configuration pair receives an independent calibration-only equal-error threshold. Evaluation probes never select or tune that threshold. Held-out evaluation reports verification accuracy, EER, FAR, FRR, TAR at FAR 1% and 5%, top-1/3/5 identification, known open-set correctness, Unknown rejection, false-known attribution, known false-Unknown decisions, and valid-output/failure counts.

The literal `Unknown` is assigned when the best enrolled score is below the calibrated threshold. A failed Unknown probe is not credited as a correct rejection. Score distributions separately summarize target, different-known, and Unknown-impostor scores.

## Statistical analysis

Primary intervals use a speaker-level cluster bootstrap with seed 3800, 500 repetitions, and 95% intervals. Repeated probes from one person are never treated as independent bootstrap units. Configuration tables retain each deterministic enrollment repetition; curve tables summarize matched repetitions and expose between-configuration variability. Effect sizes, reference deltas, and confidence intervals are emphasized; the tool does not generate dozens of uncorrected significance tests.

The high-information reference is five natural enrollment utterances, normalized-mean aggregation, and natural full probes. `quality_loss_vs_reference.csv` reports candidate-minus-reference changes without inventing a non-inferiority margin.

## Analysis and product interpretation

`Analyze` writes configuration and speaker tables, enrollment/duration curves, aggregation comparisons, joint-frontier rows, reliability intervals, subgroup descriptions, speaker diagnostics, quality-loss deltas, a report, and plots. The most safety-critical outputs are false-known attribution versus probe duration and known-speaker correct identification versus probe duration.

Subgroup outputs always retain speaker/trial counts and missingness. The very small oldest age groups cannot support strong inferential conclusions. Difficult speakers remain in the results.

`Collect` packages compact analysis and frozen manifests for later interpretation while referencing, not copying, large biometric-sensitive embeddings.

## Limitations

1. Common Voice is prompted/read speech and does not establish spontaneous conversational or target-device performance.
2. File-start prefix duration is available waveform duration; precise active-speech boundaries are unavailable.
3. Session/device diversity is unavailable.
4. Age, gender, accent, and variant metadata are self-reported and unevenly populated; tiny subgroups are descriptive only.
5. A backend's minimum technically accepted duration is empirical. Very short slices may be invalid and are not padded.
6. The 20-second budget reduces the known cohort from 272 to 243 before the paired probe requirement, and the final core is 221.
7. Ten-second probe prefixes are not scientifically supported by the v1 paired cohort.
8. Clean/reference enrollment is primary; target-domain devices and approved acoustic stress confirmation remain later work.
9. No automatic reliability threshold, non-inferiority margin, enrollment policy, or live-delay policy is encoded.

See `app/speaker_enrollment/README.md` for exact Anaconda Prompt, Command Prompt, and PowerShell commands, inputs, outputs, phase controls, analysis, collection, and tests.
