# H2 product-pipeline scientific controller

## Causal session-memory and short-turn study

The development program executes M0-M5 across the five declared expiry cells
with the real identity state primitive and checksum-bound runtime events; it
does not synthesize per-policy projections. M4 adds an active-roster ordering
prior while still completing the exact full gallery before every decision and
uses source-time confidence decay that can release, but never create, a name.
M5 adds causally bounded cluster reconciliation using a threshold calibrated
only on development-calibration identities. The A-E short-turn comparison uses
the same primitive and remains advisory until production exposes a bound A-E
policy switch. Purpose, inputs, outputs, restart behavior, commands, and metric
scope are documented in [CAUSAL_MEMORY_README.md](CAUSAL_MEMORY_README.md).

## Purpose

This package controls the fixed H2 product program without putting model logic
in the controller. It schedules only these two matrix rows:

- `fullpipe_v1_ag_dr_ir` — Sherpa Giga + Pyannote Segmentation 3.0 + ReDimNet2-B2;
- `fullpipe_v1_ao_dr_ir` — Original Sherpa reduced fallback/regression using the
  same H2 speaker stack.

All neural work runs through the existing `app.full_pipeline` runtime and
`app.full_pipeline_evaluation.worker`. The H2 controller adds restart-safe job
state, strict tuning identities, development-only successive halving, an
immutable development/evaluation firewall, automatic phase transitions, and a
readable monitor. It does not duplicate inference. The model-free
`reporting.py` layer validates every predeclared result and source checksum,
keeps conditional and end-to-end metrics separate, answers the 18 steering
questions, and creates a two-pass allowlisted reproducibility ZIP. It cannot
turn incomplete, unsupported, or corrupt evidence into program completion.

The program's 192-hour/eight-day figure is an advisory planning target. There
is no automatic wall-clock cutoff. One accuracy job runs at a time in the
current conservative controller (the protocol permits at most two), and every
matched resource job is serial.

The current default is the corrected `v17` campaign. Every stopped `v1`–`v16`
workspace, its completed atomic cases, partial result trees, logs, and incident
history remains preserved on C: and is never overwritten or silently promoted.
V13 retains v12's M4/M5 completion, event-to-episode metrics, metadata-stratified
short-turn panels, formula-preserving portable reductions, and measured-evidence
fine-tuning handoff. It corrects the integrated-enrollment source allocator:
the exact integer-frame duration budget is now distributed as evenly as possible
across all three or five enrollment recordings. Two predeclared attempts remain
source-disjoint, varied-session attempts still span two chapters, and every
slice must satisfy the ReDim minimum and source bounds. The installed
train-clean-100 preflight qualifies 64 disjoint speakers and all 32 cells.

V14 preserves those completed scientific improvements and adds a machine-
validated safety-selection contract: every result-affecting selector minimizes
wrong-known risk before stranger false-known risk. V13 was stopped at an atomic
development boundary before policy freeze or held-out access; its valid Phase
1/2 evidence remains checksum-bound and is not silently reinterpreted.

V12 stopped gracefully after 25 complete jobs and 1,746 sealed cases when the
real-data preflight exposed the old allocator defect; its checksum-bound
supersession receipt preserves those results. Held-out evaluation was never
opened. No evaluation reference content was inspected by the correction.
Scientifically identical neural products may still be reused from the shared
content-addressed cache after their hashes validate.

## Scientific safety properties

- Every workspace, result, summary, and cache path must resolve to drive `C:`.
- A graceful stop is observed only before the next case or after the current
  complete case. It never kills inference midway through an atomic case.
- Every ordinary runtime case is first sealed as its own checksum-bound shard.
  A restart reuses each valid case, reruns only a missing or corrupt shard, and
  deterministically rebuilds the aggregate. After immediate shard checksum
  validation, the regenerable per-case runtime tree is deleted to protect the
  C: reserve; a later restart also removes any completed crash leftover.
  Failed/partial case trees, shared caches, model assets, enrollment profiles,
  and source audio remain available for diagnosis or reuse.
- Optional medium/full successive-halving jobs are promoted only from
  development metrics. Non-promoted jobs become `SUPERSEDED`, not “complete.”
- Boundary-correction and overlap-policy sweeps are isolated one-axis
  comparisons against the same historical baseline. Consequently, an overlap
  result correctly records the baseline boundary value rather than the newly
  selected boundary value. Each sweep writes its own immutable development-only
  receipt; `_frontier_runtime_configuration` later validates both receipts and
  composes their selected values into the strict integration, calibration,
  freeze, demo, and held-out tuning. This avoids confounding the overlap result
  while still preventing a stale baseline axis from entering the final runtime.
- The small and medium halving panels are nested, scenario-stratified, and
  independently qualified to contain nonzero development reference speech in
  every frozen short-turn duration bin. The metric denominator is audited at
  protocol preparation and again at runtime through fail-closed promotion.
- Held-out case membership is predeclared, but optimized tuning is not faked by
  the historical baseline. Freeze creates a second immutable held-out execution
  manifest whose job identity binds the freeze checksum and strict selected
  `H2RuntimeTuning` checksum.
- A replay handler may contribute selected executable axes only when its result
  is checksum-bound, says `development_only_selection=true` and
  `evaluation_material_inspected=false`, and lists `selected_runtime_axes`.
  Conflicting or out-of-scope axes fail closed.
- A research job with no valid implementation is marked failed/blocked. It is
  never silently counted as a completed study.

The non-neural scientific layer in `science.py` implements:

- maximum-gallery open-set calibration at 0.1%, 0.5%, 1%, 2%, and 5% target
  FPIR, with score, Top-1/Top-2 margin, evidence, consistency, gallery scaling,
  known/wrong/Unknown outcomes, and identity hubness. Each row records the
  eligible stranger-speaker/cluster counts, empirical FPIR resolution, and the
  one-sided exact 95% binomial upper bound when zero strangers are falsely
  identified. A target below the cohort resolution is explicitly
  `NOT_DEMONSTRATED`; an empty quality/margin gate uses a finite reject-all
  score above every calibration score;
- a checksum-bound, source- and speaker-disjoint development
  calibration/selection firewall. A bounded deterministic metadata-only search
  uses pseudonymous speaker IDs to form two non-overlapping probe-speaker
  cohorts; whole recordings that bridge the cohorts are explicitly labelled
  `excluded_cross_cohort` and cannot enter policy fitting or selection. The
  partition reads no predictions, metrics, transcripts, or acoustic content
  and never falls back to the older sparse 20% assignment. Both roles retain
  the same predeclared enrolled gallery because the gallery is the fixed
  open-set decision population; the disjointness claim applies to probe-audio
  speakers, not to those fixed enrollment templates;
- causal memory/hysteresis and short-turn replay whose transitions use scores,
  current-frame event order, source time, cluster identity, last real evidence,
  overlap/contradiction flags, and prior state only. Replay calls the same
  `SessionIdentityManager` transition implementation as the live runtime.
  M4's active roster changes only evaluation order: a set-equality assertion
  proves the full enrolled gallery is completed before a decision. Its
  exponential decay uses source time and can only release an identity. M5
  averages actual full-gallery score signatures, uses timing/non-overlap
  constraints, requires two embeddings per fragment, calibrates its threshold
  on development-calibration speakers only, then freezes it before selection
  scoring. Spatial/XVF inputs remain inactive and have no result effect.
  Reference truth is copied only after each transition for scoring;
- exact H0/H1/H2A/H3/H4 by 15/30/60/120-second/end-session hysteresis coverage,
  including adaptive-policy outcome cells and consecutive release passes. Base
  threshold metadata is not presented as event-specific effective-threshold
  telemetry. The
  M0-M5 by expiry table is also exhaustive; a cell without causal turn,
  re-entry, decay, or reconciliation evidence is checksum-bound as
  `UNSUPPORTED_CAPABILITY` and receives no invented metric;
- transcript-policy selection among four actual post-selection runtime result
  trees, while preserving the already-materialized boundary/overlap choice;
- a sealed, development-only 32-cell enrollment confirmation (3/5 exact
  utterances, exactly 10/20 seconds, single/varied LibriSpeech sessions,
  normalized mean/exact frozen ReDim `multi_template_max`, and
  blind/quality-filtered acceptance). Calibration-known,
  calibration-stranger, selection-known, and selection-stranger speakers are
  disjoint; enrollment uses session A or A+B while probes use held-out session
  C. The panel is fixed with seed 3800 and content hashes before inference.
  Historical Common Voice rows remain `HISTORICAL_STANDALONE_*` and are never
  called integrated or given an inferred session/QC axis. ReDim vectors exist
  only in the private restart cache; public evidence contains hashes/scalars.
  The integrated selected cell is advisory because its 16-speaker gallery is
  not the frozen full H2 gallery. Freeze therefore preserves the historical
  three-clean-utterance/~10-second/`multi_template_max` application policy
  unless a later matched full-gallery calibration proves compatibility;
- whole-speaker-cluster hierarchical bootstrap. Every sampled speaker retains
  all of that speaker's probes/cases; a K-speaker case contributes 1/K to each
  speaker in both the point estimate and every draw. Rows without speaker IDs
  use explicit case-level fallback units, and ratio metrics retain their
  numerator/denominator sufficient statistics.

`embedding_clustering_coverage.csv` accounts for every declared embedding
window, hop, voiced-proportion, non-overlap, accumulation, aggregation,
outlier, R1-R4 reuse, clustering-threshold, and attach-gap cell. A cell is
either checksum-bound `MEASURED` or an explicit `UNSUPPORTED_CAPABILITY` with
a reason and no synthetic metric. R1/R2 resource claims require their matched
serial resource receipts; R3/R4 require their paired parity receipts.

Version 15 corrects two resource-evidence defects discovered during the v14 R1
run. `R1_TWO_INDEPENDENT_MODELS` now assigns the diarization and identity roles
to distinct semantic worker-pool partitions, so it launches two independent
ReDimNet processes even though both use the same backend and checkpoint.
`R2_ONE_SHARED_MODEL` still aliases both roles to one process intentionally.
Partitions are stable across case-specific worker IDs, preserving process reuse
between serial cases. The frozen enrollment/gallery preparer joins the identity
partition, so it cannot accidentally collapse the R1 diarization worker into
the same process. Worker status records the partition ID for auditability.

Version 15 also reads the runtime's nested bounded-queue contract and preserves
`maximum_observed_depth`, dropped frames, total blocked time, and maximum single
block duration in each case shard. A full queue under the `block` policy is
therefore reported as backpressure rather than as a zero-depth queue or a stuck
runtime. The v14 R1 resource rows and v14 sealed `maximum_queue_depth` values
are retained as superseded provenance and must not be used for final resource
ranking. Accuracy evidence is not silently relabelled; the v15 runtime identity
and campaign outputs are independently checksum-bound.

Version 16 makes the R2 one-model claim independent of enrollment-cache state.
The v15 runtime assigned its shared diarization/identity model to the
diarization partition while frozen gallery preparation owned the identity
partition. A gallery cache hit kept that second worker lazy in the observed
baseline, but a miss could have left two ReDimNet processes resident. In v16,
R2/R3/R4 put their aliased runtime model in the identity partition used by
gallery preparation. R1 continues to use distinct diarization and identity
partitions. Thus R1 always has two ReDimNet processes and R2 always has one,
whether enrollment embeddings hit or miss the cache.

Version 17 transparently supersedes the blocked v16 development run after the
R3 comparator exposed two implementation defects before policy freeze and before
held-out access: a second normalization of an already-normalized FP32 reuse
vector changed a few low bits, and run-local event IDs/absolute sequence counters
were incorrectly treated as product semantics. The original 1e-6 numeric
threshold is unchanged. V17 compares the directly measured scalar delta against
that frozen threshold, excludes only run-local identifiers while retaining event
order and substantive payloads, and records a failed reuse candidate as a
non-promotable scientific outcome instead of halting the safe R2 program. All
v16 files and results remain preserved as checksum-bound superseded evidence.

R3/R4 reuse candidates are complete only after checksum-bound paired embedding
cosine/max-absolute error, raw score, Top-1, Top-2, margin, known/unknown
decision, anonymous cluster assignment, transcript-label, and complete semantic
event-sequence parity is measured and passes. They must also measure fewer
embedding calls and at least one reuse hit; parity alone cannot promote either
strategy. R3 qualifies without selecting a runtime axis. R4 first revalidates
the checksum-bound R3 result, then performs the only deterministic combined
R2/R3/R4 Pareto/lexicographic selection. A measured scientific rejection is published as `GATED_NOT_PROMOTED`, remains
ineligible for promotion, and leaves safe R2 available; an unmeasured or
structurally incomplete placeholder still blocks final analysis.

### Measured R3/R4 ReDim reuse frontier

The two phase-2 `embedding_reuse_parity` jobs call the common runtime with real
ReDimNet2-B2 inference on the same bounded development inputs: the shortest
predeclared enrolled-known/mixed case and the shortest all-unknown case. No
held-out/evaluation case is opened. The shared R2 baseline is checksum-reused
between the R3 and R4 jobs, so the unique paired workload is six logical case
executions (R2, R3, and R4 across two cases), 139.333125 seconds of processed
audio. These are scientific qualification runs, not synthetic-vector tests.

`R3_EXACT_WINDOW_EMBEDDING_REUSE` satisfies an identity request with the prior
diarization vector only when normalized PCM bytes, source and assignment sample
bounds, duration, preprocessing, normalization, backend, model, checkpoint,
and config hashes are identical. `R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION`
adds an identity-specific finite/duration/level/voicing/clipping gate, then
retains the existing duration-weighted recent-versus-accumulated identity
aggregation. A missing, non-equivalent, or rejected window always performs a
fresh identity embedding and records the reason.

Private paired artifacts live below
`automated_runs/h2_complete_product_pipeline_v17/private_embedding_reuse_parity_v1/`.
They include a common input/code/tolerance contract, restart-safe case shards,
compact measurements, receipts, and progress. Window observations contain
hashes/scalars and counters, never vectors. After a successful compact
measurement is checksum sealed, its isolated probe-embedding cache is deleted;
shared enrollment/model caches are not. Raw gallery score diagnostics remain
biometric-sensitive/private and are allowlist-excluded from the final ZIP.

The normal application, live runtime, and held-out execution default to
`emit_identity_score_diagnostics=false`. Only the checksum-bound development
post-promotion integration and private paired qualification enable it. The
worker rejects that flag outside development before constructing a model
runtime, and excluded cross-cohort development cases are not loaded or scored.
The portability handler performs explicit ONNX export, component checks, and a
fresh same-input native-versus-ONNX full-pipeline comparison before preparing
the Linux ARM64 package. The target classification remains
`PORT_REQUIRES_WORK`; desktop parity never claims ARM64 hardware validation.
These Phase-6 handlers execute in their immutable manifest order: application
validation, FP32 export, frozen-fixture parity, ARM64 package preparation,
development long-session/reliability work, then the three serial resource
measurements. The restart-safe scheduler always chooses the first pending entry
in a phase, and a failed job prevents later entries from running.
Long-session and reliability jobs use their dedicated handler and fail closed
if measured prerequisites are unavailable.

Phase 6 also schedules `app_validation`. This model-free gate runs the current
live-device/UI, file-session/export, enrollment, and embedding-inspector test
set, plus compilation and Ruff checks. Its receipt binds every test and source
hash and cannot claim physical-microphone performance. Freeze and final
reporting reject a stale, missing, or failed receipt.

### Identity-policy version and invalidation scope

The historical frozen H2/H4/H5 decision-policy hashes retain their original
behavior: two confirmations and one failed decision to release. They are
labelled internally as `LEGACY_TWO_CONFIRM_ONE_RELEASE`; their hashes are not
reused for the corrected H1 rule. `H1_TWO_CONFIRM_TWO_RELEASE` and the other
named hysteresis policies become executable only through an explicit
`h2-runtime-tuning.v2` mapping. That complete mapping, including release count,
adaptive duration gates, expiry mode, and optional M0-M3 level, receives a new
runtime-tuning SHA-256 and an `h2_product_runtime.v2:<sha256>` policy ID.

Consequently, existing historical score/vector evidence is preserved, but any
runtime result whose behavior depends on a named H policy or the new tuning
fields must be rerun or replayed under the v2 identity. Loading a v1 tuning is
supported only for its original fields; a v1 payload that attempts to carry an
unhashed v2 field is rejected.

Every dedicated handler validates its measured prerequisites and stops the
program at that job if evidence is missing or invalid; it never manufactures a
completion. After repairing a genuine failed prerequisite, use `Resume
-RetryFailed` to continue.

### Long-session and reliability handler

The phase-6 `long_session` and `reliability` jobs are implemented in
`reliability.py`. The controller supplies the final selected, strict
`H2RuntimeTuning`; execution fails closed if its product mode differs from the
logical job. The handler then calls the common true-streaming file runtime used
by the extended evaluation package. It contains no ASR, diarization, embedding,
or identity inference implementation of its own.

Long-session source selection is metadata-only. It requires exactly four
development and eight presealed held-out `product_v2` recordings whose scenario
declares `long_session=true`; ordinary core-panel members are not relabelled as
long streams. Each source is checksum-verified and deterministically
repeated/truncated to exact 30- and 60-minute mono 16-kHz WAVs on `C:`. The eight
development streams and sixteen post-freeze evaluation streams use source-clock
pace `1.0` and an empty enrollment directory. Evaluation opens only after freeze
and performs no recalibration. These are controlled prerecorded loopbacks, not
physical microphone tests.

The reliability matrix records explicit `PASS`, `FAIL`, or `UNSUPPORTED`
outcomes for sample-rate mismatch, silence, continuous input, sudden stop, ASR
worker restart, queue pressure, a deliberately slow/coalescing UI consumer, no
enrollments, a corrupt profile, file end, repeated sessions, and an in-session
reset followed by a fresh runtime restart. Device enumeration is recorded, but
microphone selection and hardware reconnect remain `UNSUPPORTED` unless a
future deterministic hardware injection boundary is connected. The handler
never converts device enumeration alone into evidence of physical behavior.

For each runtime attempt, the handler records event/revision counts,
completion, queue depth and dropped frames, deadline counters when emitted,
event-source-clock RTF, peak process-tree RSS when emitted, and bounded session
cardinalities over source time. After all compact measurements, assertions, and
tuning evidence have been extracted for a successful atomic item, only that
attempt's regenerable `runtime` tree is removed. The removal is strictly
contained to its exact numbered attempt and happens before the compact
subresult is checksum-sealed. Failed or stopped attempts are never cleaned and
remain under their numbered attempt directories for diagnosis. A successful
long stream's generated WAV and materialization sidecar are removed only after
the compact subresult has been published and revalidated; source audio is never
removed. Checksum-bound cleanup receipts record removed/retained file and byte
counts, and the job result includes aggregate cleanup counters. A path escape,
unexpected target type, deletion failure, or invalid subresult seal fails
closed without deleting the suspect target. Reuse requires the same job,
protocol, selected tuning, product mode, result-affecting code hashes, and an
exact checksum tree after compaction.
Progress and heartbeats are written durably after each complete stream/fault
boundary and during a running source-clock stream. A graceful stop finishes the
current atomic stream/fault; it never labels a half-stream complete. The 35-GiB
C: reserve is checked before every new ordinary case, long stream, and fault.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| Program configuration | `configs/automated_evaluation/h2_product_program.v17.yaml` | Fixed architecture, modes, panels, search axes, safety order, and advisory budget |
| Pipeline matrix | `configs/automated_evaluation/full_pipeline_matrix.v1.yaml` | Exact AG-H2 and AO-H2 model/checkpoint identities |
| Runtime configuration | `configs/automated_evaluation/full_pipeline_runtime.v1.yaml` | Existing backend-neutral runtime settings |
| Prepared development cases | `benchmarks/full_pipeline/full_speech_pipeline_v1/development/case_manifest.jsonl` | Development-only search and calibration cases |
| Declared long recordings | four development plus eight presealed evaluation `product_v2` rows with `scenario.long_session=true` | Provenance-bound sources for exact 30/60-minute controlled loopbacks; evaluation opens only after freeze |
| Prepared evaluation cases | `benchmarks/full_pipeline/full_speech_pipeline_v1/evaluation/case_manifest.jsonl` | Untouched held-out cases opened only after freeze |
| Installed local datasets/assets | paths referenced by prepared case manifests | Audio and enrollment material; no implicit download is allowed |
| Causal runtime trace | post-promotion strict event log and private full-gallery score diagnostics | Development-only event sequence, exact turn bounds, cluster ID, overlap/contradiction state, full-gallery scores, and assignment checksum; absence yields explicit unsupported rows rather than projection |
| Historical enrollment configuration table | checksum-inventoried ReDimNet `analysis/configuration_results.csv` | Reused only for exact five-axis integrated cells; no broad enrollment rerun |

### v6 speaker-attribution scoring contract

Protocol v6 corrects the result adapter before held-out evaluation. It does not
change audio, neural inference, enrollment, thresholds, product modes, or data
membership. Its scoring inputs are the checksum-bound reference speaker
segments/transcripts, final runtime transcript spans, anonymous diarization
segments, visible `Speaker_N`/known-name labels, identity overlay, and ordered
runtime revision events.

- Session-anonymous consistency uses only stranger duration carrying a
  session-local `Speaker_N`/`Unknown_N` label. Early generic Unknown duration is
  retained separately and no longer makes the consistency metric unsupported.
- cpWER retains every hypothesis word. A span without speaker evidence receives
  its own deterministic unassigned stream instead of disappearing.
- Speaker-attributed WER canonicalizes anonymous clusters using the frozen
  time-overlap diarization mapping, while enrolled labels are matched exactly;
  lexical text never chooses the speaker mapping.
- Non-overlap reference cases use a deterministic global Levenshtein word
  alignment (match/substitution, deletion, insertion tie order) to report word
  speaker-label accuracy, correctly transcribed-and-attributed word rate,
  wrong-speaker word count, and the unlabelled/generic word rate.
- Cross-speaker-overlap word alignment remains explicitly unsupported without
  word timestamps. Exact wrong-speaker word time also remains unsupported when
  reference word durations are absent. Segment-level timing is not presented as
  fabricated word timing.
- Ordered transcript revision events now supply the retroactive-correction
  metric. The selection code uses the catalog identifier
  `correct_transcribed_attributed_word_rate` exactly.

Outputs are ordinary per-case and aggregate metric documents, with applicable
and unsupported recording counts and the frozen alignment/mapping policy IDs.
The preserved v5 result trees remain immutable historical/superseded evidence.

### v7 development-promotion result adapter

Protocol v7 preserves the v6 scoring definitions and corrects how development
promotion reads the common evaluator result tree. Speaker-transcription metrics
are read from the `speaker_transcription` subview of `metrics/asr.json`, and UX
metrics are read from the `ux` subview of `metrics/streaming.json`. The reader
fails closed on a missing category-to-result-view mapping and selects the exact
declared subview instead of scanning unrelated subviews. This ensures
wrong-name dwell, correctly transcribed-and-attributed word rate, and transcript
revisions enter Pareto/lexicographic promotion when they are computed. The
gracefully stopped v6 run remains preserved as superseded pre-selection
evidence; it never opened held-out data.

### v8 historical-evidence reconciliation

Protocol v8 preserves every v7 scientific setting and adds a fail-closed final
reporting contract for the historical evidence named in the study. The report
re-reads the frozen H2, standalone Pyannote+ReDimNet2, and ReDimNet2 enrollment
values from their checksum-bound CSV/JSON artifacts. It writes
`historical_evidence_reconciliation.json`, reports any fresh baseline value and
descriptive delta where units match, and explains why the old and new protocols
are not causal equivalents. Missing same-unit current metrics remain explicitly
historical-only instead of being replaced or treated as zero. These descriptive
cross-protocol deltas are forbidden from development selection. The gracefully
stopped v7 run is preserved and never opened held-out data.

Optional command-line path overrides are `--workspace`, `--results-root`,
`--summary-root`, and `--config`. Overrides must also be on `C:`.

## Outputs

The default locations are:

- controller state and immutable manifests:
  `automated_runs/h2_complete_product_pipeline_v17/`;
- scientific result trees:
  `JustPeachyResults/full_pipeline/h2_complete_product_pipeline_v17/`;
- reports, frozen configurations, inventory, and compact package:
  `JustPeachyResearchSummaries/h2_complete_product_pipeline_v17/`.

Important files include:

- `program_state.json` — program/job lifecycle;
- `protocol_manifest.json` and `job_manifest.json` — immutable planned identity;
- `campaign.sqlite3` — shared durable development runtime queue;
- `last_queue_snapshot.json` — last checksum-independent monitor snapshot,
  retained with an explicit stale/error flag if a live queue read is transiently
  unavailable;
- `attempts/*/case_shards_v1/*/case_shard.json` and `cursor.json` — atomic
  ordinary-case restart evidence;
- `dynamic_queues/*/dynamic_execution.json` — cumulative-selection-bound
  integration, paragraph, mode, and resource executions;
- `bounded_timing_smoke.json` — optional three-case real-model timing receipt;
- `milestones.jsonl` — idempotent phase/freeze/held-out/final notifications;
- `promotions/*.json` — development-only Pareto decisions;
- `frozen_policy.json` — immutable development selection;
- `historical_evidence_reconciliation.json` — source-verified old-versus-new
  evidence with protocol-difference explanations;
- `frozen_policy.json` also records the default product mode selected only from
  the three matched development mode runs. The ordered safety-first metric
  vector, every source checksum, tie policy, and selection identity are frozen
  before held-out material opens. Held-out results may confirm or diagnose the
  choice but cannot change it;
- `JustPeachyResearchSummaries/.../frozen_configurations/h2_demo_runtime_binding.frozen.json`
  — one checksum-bound six-entry application binding for AG-H2 and AO-H2 across
  all three product modes. `LaunchDemo` automatically supplies this file and
  its expected SHA-256 after freeze; before freeze the UI is explicitly marked
  as an engineering baseline rather than a final scientific configuration;
- `heldout_execution_manifest.json` — post-freeze tuning-bound held-out jobs;
- `heldout_frozen_queue/campaign.sqlite3` — separate held-out queue;
- the exact final configuration registry:
  `h2_configuration_registry.yaml`;
- measured policy/result tables:
  `h2_segmentation_frontier.csv`, `h2_boundary_results.csv`,
  `h2_overlap_results.csv`, `h2_embedding_policy_results.csv`,
  `h2_model_sharing_results.csv`, `h2_embedding_reuse_parity.csv`,
  `h2_identity_policy_results.csv`, `h2_hysteresis_results.csv`,
  `h2_session_memory_results.csv`, `h2_short_turn_results.csv`,
  `h2_reentry_results.csv`, `h2_expiry_results.csv`,
  `h2_active_roster_results.csv`, `h2_mode_comparison.csv`,
  `h2_transcript_results.csv`, `h2_ui_latency_results.csv`,
  `h2_resource_results.csv`, `h2_long_session_results.csv`, and
  `h2_onnx_parity.csv`;

The claim-specific exports retain their complete evidence slices:
`h2_ui_latency_results.csv` includes tentative, confirmed, and stable-name
timings; `h2_reentry_results.csv` combines held-out warm/re-entry metrics with
the causal returning-turn study; `h2_expiry_results.csv` includes both named
hysteresis expiry cells and exact source-clock decay outcomes; and
`h2_active_roster_results.csv` combines M4/M5 full-gallery safety/correctness
measurements with bounded long-session roster growth. M4/M5 rows also retain
the measured confidence-decay and cluster-reconciliation parameters.
- final analysis and audit files:
  `h2_linux_portability.json`, `h2_memory_budget.json`,
  `h2_final_summary.csv`, `bootstrap_intervals.csv`,
  `failure_inventory.csv`, `analysis_manifest.json`, `REPORT.md`,
  `METRIC_GUIDE.md`, and `REPRODUCIBILITY_MANIFEST.json`;
- per-job `open_set_policy_frontier.csv`, `identity_hubness.csv`,
  `embedding_clustering_coverage.csv`,
  `memory_policy_frontier.csv`, `short_turn_replay_frontier.csv`,
  `transcript_policy_frontier.csv`, `runtime_enrollment_profiles.csv`,
  `historical_enrollment_evidence.csv`, `integrated_enrollment_matrix.csv`, and
  `bootstrap_intervals.csv` under `JustPeachyResults/.../jobs/<job>/artifacts/`;
- per-job long/reliability `job_result.json`, `checksums.json`,
  `long_session_source_plan.json`, `long_session_results.jsonl` or
  `reliability_results.jsonl`, and `session_memory_over_source_time.jsonl` under
  `JustPeachyResults/.../jobs/<job>/reliability_result/`, plus per-attempt and
  post-seal input-cleanup receipts under `cleanup_receipts/`;
- the phase-6 common-app `job_result.json`, including current test/source hashes,
  exact commands, pass counts, the five capability results, the development
  default-mode receipt, and an in-process load/resolve check of all six
  application configuration entries;
- supporting `result_file_inventory.csv`, `cache_inventory.json`,
  `evidence_table.json`, `analysis_receipt.json`, and
  `collection_receipt.json`;
- the self-validating upload artifact in `JustPeachyResearchSummaries`, named
  `h2_complete_product_pipeline_<protocol>_<timestamp>.zip`.

The compact ZIP includes the summary, final documents, frozen configurations,
protocol/job/freeze identities, controller milestones/history, small parity
JSON, and the safe files from `deployment/h2_arm64`. It excludes raw datasets,
generated/recorded audio, ONNX graphs and model weights, credentials/tokens,
biometric vectors/embeddings, databases, shared/large caches, locks, temporary
files, and any unapproved oversized file.

## Integrated enrollment confirmation: purpose, inputs, and outputs

The `integrated_enrollment` job answers whether recording count, exact total
duration, session diversity, aggregation, or real sample rejection changes the
development recommendation. It is scheduled automatically in phase 3; do not
start a separate enrollment campaign beside the controller.

Inputs are the installed development-research corpus at
`Raw Datasets (Not formatted)/LibreSpeech/train-clean-100/LibriSpeech/train-clean-100`,
the checksum-bound historical speaker-enrollment results, the frozen ReDim H2
scientific policy, and the qualified local ReDimNet2-B2 environment/model
already recorded by the backend registry. Downloads are disabled. It never
opens an H2 evaluation/held-out result.

Public outputs beside the job result are the sealed panel, public cache
manifest (hashes only), 32 historical requested cells, historical raw-row
inventory, 32 integrated cells, QC/repeat events, hubness, and exactly one
advisory selected cell. Private per-slice NPZ vectors live only below
`automated_runs/h2_complete_product_pipeline_v17/private_biometric_cache/` and
are excluded from reports and ZIPs. Restart reuses checksum-valid slices and
repairs only missing/corrupt items.

The v13/v14 duration policy is `balanced_exact_frames_per_utterance.v1`. Examples
at 16 kHz are `53,334 + 53,333 + 53,333` frames for 3 recordings/10 seconds and
`32,000` frames per recording for 5 recordings/10 seconds. The panel stores
only source SHA-256 identities and frame ranges; it does not copy the raw audio.
That preserves exact reproduction while avoiding a second audio corpus.

Complete PowerShell commands for the automatic job and its model-free focused
validation are:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_h2_product_program.ps1 -Action Run -Background -OpenMonitor
.\scripts\monitor_h2_product_program.ps1 -Follow -IntervalSeconds 30
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_integrated_enrollment.py
```

Equivalent Anaconda Prompt or Command Prompt commands are:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.h2_product_program Run
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest -q tests\test_h2_integrated_enrollment.py
```

The isolated `integrated_enrollment worker --request ...` entry point is an
internal controller interface whose request contains private source/cache
paths; the controller creates and checksum-binds it. Users should launch the
program command above instead of constructing a worker request by hand.

## Version 11 promotion and stop-boundary correction

Version 11 supersedes the preserved pre-freeze version 10 campaign. A live
scientific audit found that `R2_ONE_SHARED_MODEL`, `W150_H075`, and
`C0_CLUSTER_ATTACH_HISTORICAL` executed identical tuning but were treated as
three promotion candidates. It also found that the accuracy-equivalent R1 and
R2 execution architectures could consume both full-tier slots before their
matched serial-resource comparison ran. Version 11 therefore uses one unique
R2 baseline in successive halving, keeps one R1 small-panel accuracy reference
outside promotion, and fails preparation if any two promoted labels have the
same executable tuning.

The same audit exposed a durable-stop regression: version 10 began a new case
after sealing the current case despite an existing stop request. Version 11
checks the durable stop file directly at every worker case boundary in addition
to the in-memory poller. Version 10 was force-terminated only after it ignored
the graceful request; three completed W050 case shards, all completed results,
and all shared neural caches were preserved. Its checksum-bound
`supersession_receipt.json` records the defect and forced-stop scope. No held-out
material was opened and no development freeze existed.

Version 10 had previously corrected version 9 by binding every Python source
under `app/`, every stable file in `deployment/h2_arm64/`, and the complete
no-effect `spatial-evidence-interface.v2` contract. Version 11 retains those
protections and uses separate workspace, scientific-results, and summary roots.

Use explicit version 16 paths for the current corrected campaign:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Workspace = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17'
$Results = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17'
$Summaries = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17'
$Config = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\h2_product_program.v17.yaml'
.\scripts\run_h2_product_program.ps1 -Action Run -Background -OpenMonitor -Workspace $Workspace -ResultsRoot $Results -SummaryRoot $Summaries -Config $Config
```

## PowerShell: normal operation

Open PowerShell and run the following complete commands:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'

# Read-only audit of preserved evidence and active processes.
.\scripts\run_h2_product_program.ps1 -Action Audit

# Run a bounded three-case real-model timing calibration, then inspect the
# updated low/expected/high plan. This is not scientific result evidence.
.\scripts\run_h2_product_program.ps1 -Action Smoke
.\scripts\run_h2_product_program.ps1 -Action Plan

# Audit, Validate, Plan, Status, and LaunchDemo -DryRun are read-only.
# They do not create a custom workspace or atomic-publication receipt. The
# PowerShell wrapper rejects -DryRun for other actions.

# Prepare and deeply validate immutable scientific state.
.\scripts\run_h2_product_program.ps1 -Action Prepare
.\scripts\run_h2_product_program.ps1 -Action Validate

# Start the persistent controller and a separate monitor window. It transitions
# phases automatically, has no automatic eight-day cutoff, and starts or reuses
# the hidden checksum-validating final-package watcher.
.\scripts\run_h2_product_program.ps1 -Action Run -Background -OpenMonitor

# Follow percentage, phase/job/backend/mode, job/case/audio totals, in-case
# source-time progress, embedding/cache telemetry, worker health, RTF, CPU/RAM,
# failed jobs/recovered attempts/retries, ETA/finish time, latest output, and
# C: storage projection.
.\scripts\monitor_h2_product_program.ps1 -Follow -IntervalSeconds 30
```

The headline percentage and job/case/audio denominators come from the
controller's durable active-plan snapshot, so development candidates removed
by successive halving are not counted as remaining work. The monitor also
shows the larger predeclared-manifest ceiling as a labelled diagnostic rather
than mixing that ceiling into the headline percentage.

The read-only monitor plays the standard Windows notification sound whenever a
new durable phase/freeze/held-out/final milestone appears. Pass
`-NoMilestoneSound` to silence it. The milestone check uses the same
shared-delete read mode and never writes scientific state.

Every normal `Run` or `Resume` also starts or reuses a matching hidden
final-package watcher for the selected workspace. After the controller reaches
`COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`, the watcher verifies the native ZIP,
builds and validates the augmented reproducibility ZIP, and atomically writes
`final_augmented_collection.json` in the workspace plus
`LATEST_H2_AUGMENTED_PACKAGE.json` in the package root. These operational
pointers do not modify the controller's frozen `program_state.json`.
In follow mode, the visible read-only monitor remains open through this short
post-run augmentation step and exits only after it has independently verified
the augmented ZIP hash and printed `UPLOAD THIS FILE TO CHATGPT`, the absolute
path, and SHA-256. A failed or invalid pointer remains visible instead of being
silently treated as full-program completion.

CPU and RAM come from checksum-bound campaign telemetry when the active job
publishes live resource fields. Before those fields are available, the monitor
samples the exact controller process recorded in
`h2_program_run.lock.owner.json` and labels the values
`controller_host_process_fallback`. It separately follows the model worker's
live process tree. Worker CPU is expressed relative to one fully occupied
logical core, so a multithreaded worker may exceed 100%. The first CPU value
says `measuring` because a time delta is required. These live samples are
display telemetry only and are never used for final serial resource
comparisons.

The monitor is genuinely read-only: it opens controller snapshots with Windows
read/write/delete sharing and never calls a status path that writes a last-known
queue snapshot. It reports overall, current-job, neural/runtime, policy, and
bootstrap progress; current phase/configuration/case; case and audio totals;
the exact backend/mode; configured model-instance count; RTF/telemetry when
published; failed jobs separately from recovered attempts/retries; activity;
and C: reserve. By default it uses durable snapshots only and does not open the
rapidly replaced per-case `status.json`. This avoids a Windows
filesystem/filter-driver race observed during unattended execution while
retaining two percentage bars and sealed case counters. `Ctrl+C` closes only
the monitor.

Safe durable-snapshot mode still reports model-worker liveness, aggregate
worker RSS, and sampled CPU. It derives those values read-only from
`app.full_pipeline.worker_main` descendants of the checksum-bound controller
owner and labels the source `controller_descendant_worker_fallback`. Process
activity is diagnostic only; checksum-sealed case counters remain the
authoritative progress measure. Accuracy cases may perform work in the
controller or in workers whose lifetime is shorter than a monitor sample. When
no separate long-lived worker fleet is observed during an otherwise active
case, the console therefore says exactly that and does not label the campaign
stuck; advancing durable case activity and controller CPU are the applicable
liveness evidence.

For a short bounded diagnostic, `-IncludeLiveCaseStatus` opts into the per-case
source-duration percentage, heartbeat, embedding requests/RTF, cache
hits/misses, live runtime queue depth/delay, queue-backpressure totals, dropped
frames, and model-worker health. The JSON and console output label whether queue
depth came from `live_case_status` or the durable `campaign_progress` fallback,
so a durable snapshot cannot be mistaken for the active bounded runtime queue.
The monitor also reproduces the controller's dynamic overall-progress formula
from the immutable job manifest, durable per-job state, and queue progress: jobs
marked `SUPERSEDED` by successive halving are excluded, while zero-case freeze,
analysis, and collection jobs retain one completion unit. This keeps the
percentage, active job/case/audio totals, and ETA aligned with the authoritative
controller without opening or writing its SQLite database. These dynamic-plan
and provenance-aware queue fields are emitted by monitor schema
`h2-read-only-monitor.v7`.
Do not leave that diagnostic mode enabled during the unattended scientific
campaign on Windows.
Transient reads or `BLOCKED`/`FAILED` snapshots do not leave a stale screen;
the wrapper continues following the restart-safe controller.

Monitor inputs are `program_state.json`, `campaign_progress.json`, and
`job_manifest.json` in the selected workspace, plus the existing component
alias registry. Its only output is the console (or one JSON snapshot with
`-Once -Json`); it does not create or modify result files.

To use custom C: locations containing spaces, use this complete launch command
instead of the default launch above (never launch both workspaces at once):

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_h2_product_program.ps1 -Action Run -Background -OpenMonitor -Workspace 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\H2 Custom Product Run' -ResultsRoot 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\H2 Custom Product Run' -SummaryRoot 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\H2 Custom Product Run' -Config 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\h2_product_program.v17.yaml'
```

The wrapper resolves those values before changing directories, uses a
structured child-process argument list, puts logs under that custom workspace,
and forwards the same overrides to the monitor window.

On Windows the launcher also applies the bounded, operational-only atomic-file
publication retry documented in
`scripts/H2_WINDOWS_ATOMIC_RETRY_README.md`. Its checksum-bound policy and
append-only recovery events are stored under the campaign workspace. This does
not alter the frozen model/runtime source identity or any scientific value.
The launcher propagates the same retry to isolated Python enrollment/model
workers through a dedicated `sitecustomize` directory on inherited
`PYTHONPATH`; otherwise a controller-local `os.replace` patch would not protect
child-process progress publication. Predecessor operational-policy receipts are
retained when this propagation mechanism is upgraded.

To request a graceful case-boundary stop:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_h2_product_program.ps1 -Action Stop -StopReason 'operator_requested_pause'
```

To resume stopped work (complete checksum-valid results are reused):

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_h2_product_program.ps1 -Action Resume -Background -OpenMonitor
```

To retry a repaired failed handler explicitly:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_h2_product_program.ps1 -Action Run -RetryFailed -Background
```

For unattended Windows execution, launch the external supervisor after the
controller. It does not alter scientific code, policies, results, or frozen
hashes. It automatically relaunches only after a newly logged transient
`WinError 5`/sharing violation, expired-lease message, the runtime's explicitly
recoverable empty-JSON read signature, or the narrowly identified ReDimNet
enrollment-worker reload timeout whose process is still alive but has not
published `ready` within the frozen 90-second startup window. The latter retry
resumes through the transactional queue and preserves all sealed case shards;
it does not change model code, timeouts, thresholds, or result identity. Any
other failure is left stopped and visible for scientific review. Five
consecutive recoveries are the default safety limit, preventing an endless loop
from masking a deterministic defect; change it explicitly with
`-MaximumConsecutiveRecoveries` only after reviewing the supervisor log.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'

# Verify paths and process detection without starting a loop.
.\scripts\supervise_h2_product_program.ps1 -DryRun

# Run in a dedicated PowerShell window, or launch it hidden with Start-Process.
.\scripts\supervise_h2_product_program.ps1
```

Supervisor events are appended to
`automated_runs\h2_complete_product_pipeline_v17\logs\controller.supervisor.jsonl`.
The supervisor recognizes both quoted and unquoted `Run`/`Resume` arguments in
direct, Windows-retry, and pre-freeze-correction controller command lines. This
prevents its own hidden `Start-Process` quoting from being mistaken for a
missing controller.
Nested failed-job diagnostics are inspected as JSON, so a recoverable Windows
sharing/atomic-publication error remains detectable even when no traceback has
yet reached the controller stderr log.
There is no wall-time cutoff and no generic retry of scientific/model errors.
The ReDimNet rule matches only the exact enrollment worker, exact 90-second
startup timeout, and `exit_code=None`; a different worker failure remains
stopped for diagnosis.

If a stopped run reports `JSONDecodeError: Expecting value: line 1 column 1`,
audit the checksum-addressed runtime cache before retrying. The quarantine
utility parses only candidate-invalid JSON files, defaults to a dry run, keeps
every moved byte on C:, records source paths and SHA-256 hashes, and never
modifies scientific result trees or valid cache entries:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\quarantine_invalid_full_pipeline_cache.ps1
.\scripts\quarantine_invalid_full_pipeline_cache.ps1 -Apply
.\scripts\run_h2_product_program.ps1 -Action Resume -RetryFailed -Background
```

Quarantined entries remain recoverable under
`automated_runs\h2_complete_product_pipeline_v17\cache_quarantine`. Their
content-addressed paths are recomputed by the normal runtime on demand.

For a bounded controller check that runs at most one job, use foreground mode:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_h2_product_program.ps1 -Action Run -MaximumJobs 1
```

Do not interpret `-MaximumJobs` as the eight-day policy; it is only a manual
smoke/debug bound.

## PowerShell: status, interim reports, portability, and demo

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'

# One status snapshot.
.\scripts\run_h2_product_program.ps1 -Action Status

# Write a clearly labelled PARTIAL_NOT_PROMOTABLE diagnostic. This never writes
# final REPORT.md or authorizes collection.
.\scripts\run_h2_product_program.ps1 -Action Analyze

# Collect is final-only. It fails unless the scheduled analysis is COMPLETE and
# every scientific, portability, long-session, schema, and checksum gate passes.
.\scripts\run_h2_product_program.ps1 -Action Collect

# Inventory scheduled and measured portability evidence without overwriting it.
.\scripts\run_h2_product_program.ps1 -Action ExportPortable

# Verify the GUI launch command without opening a window, then launch it.
.\scripts\run_h2_product_program.ps1 -Action LaunchDemo -DryRun
.\scripts\run_h2_product_program.ps1 -Action LaunchDemo
```

Direct ONNX export/parity commands (use explicit local graph paths; `.onnx`
graphs are model artifacts and are never placed in the compact final ZIP).
Export and component parity must run in each component's pinned native worker
environment; the controller base `.venv` deliberately does not carry this
toolchain. The autonomous Phase 6 jobs use these same interpreters and try the
preferred Dynamo exporter before any separately recorded legacy fallback:

```powershell
$Repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$RedimPython = Join-Path $Repo '.stage8-envs\redimnet2\Scripts\python.exe'
$SegmentationPython = Join-Path $Repo '.stage8-envs\credential-diarization\Scripts\python.exe'
$Out = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17\portability_artifacts'
$RedimGraph = Join-Path $Out 'redimnet2_b2_fp32.onnx'
$SegmentationGraph = Join-Path $Out 'pyannote_segmentation_3_0_fp32.onnx'
$Parity = Join-Path $Out 'parity'

& $RedimPython -m app.h2_portability export --component redimnet2_b2_speaker_embedding --onnx-path $RedimGraph --exporter torch_onnx_dynamo_v1
& $SegmentationPython -m app.h2_portability export --component pyannote_segmentation_3_0 --onnx-path $SegmentationGraph --exporter torch_onnx_dynamo_v1
& $RedimPython -m app.h2_portability parity --component redimnet2_b2_speaker_embedding --onnx-path $RedimGraph --output-dir $Parity
& $SegmentationPython -m app.h2_portability parity --component pyannote_segmentation_3_0 --onnx-path $SegmentationGraph --output-dir $Parity
& $RedimPython -m app.h2_portability arm64-diagnostic --require-graphs --redim-onnx $RedimGraph --segmentation-onnx $SegmentationGraph
```

Common application, direct live microphone, exact-path file simulation, and
enrollment CLI commands:

```powershell
$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe'
$ConfigurationRegistry = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\h2_configuration_registry.yaml'
$RuntimeConfig = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\frozen_configurations\h2_demo_runtime_binding.frozen.json'
$RuntimeConfigSha256 = (& $Python -c 'import pathlib, sys, yaml; print(yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["demo_runtime_binding"]["sha256"])' $ConfigurationRegistry).Trim().ToLowerInvariant()
$ObservedRuntimeConfigSha256 = (Get-FileHash -LiteralPath $RuntimeConfig -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ObservedRuntimeConfigSha256 -ne $RuntimeConfigSha256) { throw 'Frozen H2 runtime binding checksum mismatch' }
& $Python -m app.full_pipeline_demo launch --h2-runtime-config $RuntimeConfig --h2-runtime-config-sha256 $RuntimeConfigSha256
& $Python -m app.full_pipeline_demo devices
& $Python -m app.full_pipeline_demo live --pipeline-id fullpipe_v1_ag_dr_ir --duration-sec 30 --h2-runtime-config $RuntimeConfig --h2-runtime-config-sha256 $RuntimeConfigSha256
& $Python -m app.full_pipeline_demo file --pipeline-id fullpipe_v1_ag_dr_ir --input 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_a0281.wav' --pace 1 --h2-runtime-config $RuntimeConfig --h2-runtime-config-sha256 $RuntimeConfigSha256
& $Python -m app.full_pipeline_demo enroll-record --pipeline-id fullpipe_v1_ag_dr_ir --display-name 'Person Name'
& $Python -m app.full_pipeline_demo enroll-import --pipeline-id fullpipe_v1_ag_dr_ir --display-name 'CMU Arctic AEW Demo' --wav 'prompt_1=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_a0281.wav' --wav 'prompt_2=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_a0282.wav' --wav 'prompt_3=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_a0283.wav'
```

These final exact-binding commands are for use after final reporting creates
both `$ConfigurationRegistry` and `$RuntimeConfig`. The expected binding hash
comes from the separately packaged registry; do not derive the expected value
from the binding itself. After development freeze but before final reporting,
the controller's checksum-bound freeze job result is the authority. Before
freeze, omit the two runtime-config flags only for an explicitly non-final
engineering session. Omitting `--product-mode` uses the development-selected
default embedded in the verified binding; pass a mode explicitly only when
intentionally demonstrating another frozen mode.

After the controller reports `COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`, add the
required checksum-bound presentation plots without modifying the native
validated ZIP:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe'
& $Python .\scripts\augment_h2_final_package.py
```

The augmented package preserves every native member byte-for-byte, adds only
derived SVGs and controller-bound axis-selection receipts, validates its new
complete inventory, and prints the final upload path and SHA-256. Detailed
inputs, outputs, PowerShell, Anaconda Prompt, validation, and failure behavior
are documented in `scripts/H2_FINAL_PACKAGE_SUPPLEMENT_README.md`.

Background controller logs are written in the selected workspace's `logs`
directory; with the defaults this is
`automated_runs/h2_complete_product_pipeline_v17/logs/`. Workspace, results,
summary, and config overrides containing spaces are resolved before launch and
forwarded unchanged to the monitor.

## Anaconda Prompt or ordinary Command Prompt

The repository's project virtual environment is used directly, so activating a
different Conda environment is unnecessary. These commands work in Anaconda
Prompt and `cmd.exe`:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
set "H2_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe"
set "H2_WORKSPACE=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17"
set "H2_RESULTS=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17"
set "H2_SUMMARIES=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17"
set "H2_CONFIG=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\h2_product_program.v17.yaml"

"%H2_PYTHON%" -m app.h2_product_program Audit --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
"%H2_PYTHON%" -m app.h2_product_program Smoke --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
"%H2_PYTHON%" -m app.h2_product_program Plan --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
"%H2_PYTHON%" -m app.h2_product_program Prepare --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
"%H2_PYTHON%" -m app.h2_product_program Validate --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
"%H2_PYTHON%" -m app.h2_product_program Run --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
"%H2_PYTHON%" -m app.h2_product_program Analyze --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
"%H2_PYTHON%" -m app.h2_product_program Collect --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%"
```

`Analyze` is safe before the campaign finishes because it writes only a
non-promotable partial diagnostic. `Collect` is intentionally not partial and
returns an error until the controller-complete analysis receipt and every
required result are checksum-valid.

The direct `Run` command remains attached to that prompt. Open a second prompt
for the monitor:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
set "H2_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe"
set "H2_WORKSPACE=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17"
set "H2_RESULTS=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17"
set "H2_SUMMARIES=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17"
set "H2_CONFIG=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\h2_product_program.v17.yaml"
"%H2_PYTHON%" -m app.h2_product_program Status --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%" --watch --interval-sec 5
```

Request a graceful stop from another prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
set "H2_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe"
set "H2_WORKSPACE=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17"
set "H2_RESULTS=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17"
set "H2_SUMMARIES=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17"
set "H2_CONFIG=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\h2_product_program.v17.yaml"
"%H2_PYTHON%" -m app.h2_product_program Stop --workspace "%H2_WORKSPACE%" --results-root "%H2_RESULTS%" --summary-root "%H2_SUMMARIES%" --config "%H2_CONFIG%" --reason operator_requested_pause
```

## CLI action contract

| Action | Effect |
|---|---|
| `Audit` | Rebuild the plan in memory and verify fixed H2/C:/budget invariants; no campaign starts |
| `Prepare` | Write/verify manifests, state, and the development runtime queue |
| `Validate` | Recompute identities and verify state, queue, firewall, and completed result trees |
| `Plan` | Show all phase counts and nominal hours without running inference |
| `Smoke` | Run/reuse three real development cases for a low-confidence timing calibration; never scientific evidence |
| `Run` | Reuse/run eligible jobs and automatically advance successful phases |
| `Resume` | Explicit alias for restart-safe `Run`; checksum-valid work is reused |
| `Status` / `Monitor` | One JSON snapshot or a continuously refreshed readable screen |
| `Stop` | Request a graceful stop at a complete case boundary |
| `Analyze` | Write `partial_analysis/` as `PARTIAL_NOT_PROMOTABLE`; the scheduled analysis job alone may publish final outputs |
| `Collect` | Fail closed unless scheduled analysis and all evidence are complete; stage, validate, ZIP, rescan, and emit upload path/SHA |
| `ExportPortable` | Inspect immutable export/parity/ARM64-preparation receipts without fabricating hardware readiness |
| `LaunchDemo` | Launch the common H2 demo in a separate process |

Actions are case-insensitive. A failed research handler is not retried
implicitly; use `--retry-failed` only after fixing or connecting the handler.

## Tests

Run the bounded controller tests (no neural campaign):

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_product_program_controller.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_causal_memory.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_product_program_science.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_science_correctness.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\full_pipeline\test_identity_alignment.py tests\full_pipeline\test_h2_product_modes.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_product_program_reliability.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_product_program_reporting.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_embedding_reuse.py tests\full_pipeline_evaluation\test_h2_worker_firewalls.py tests\full_pipeline_evaluation\test_worker_integration.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m ruff check app\h2_product_program app\full_pipeline\identity.py app\full_pipeline\product_modes.py app\full_pipeline_evaluation\worker.py tests\test_h2_product_program_controller.py tests\test_h2_product_program_science.py tests\test_h2_science_correctness.py tests\full_pipeline\test_identity_alignment.py tests\full_pipeline\test_h2_product_modes.py tests\test_h2_product_program_reliability.py tests\test_h2_product_program_reporting.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m compileall -q app\h2_product_program app\full_pipeline\identity.py app\full_pipeline\product_modes.py tests\test_h2_product_program_science.py tests\test_h2_science_correctness.py tests\full_pipeline\test_identity_alignment.py tests\full_pipeline\test_h2_product_modes.py
```

The equivalent bounded science/runtime-policy and reliability checks in
Anaconda Prompt or `cmd.exe` are:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest -q tests\test_h2_causal_memory.py tests\test_h2_product_program_science.py tests\test_h2_science_correctness.py tests\full_pipeline\test_identity_alignment.py tests\full_pipeline\test_h2_product_modes.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest -q tests\test_h2_product_program_reliability.py tests\test_h2_product_program_reporting.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest -q tests\test_h2_embedding_reuse.py tests\full_pipeline_evaluation\test_h2_worker_firewalls.py tests\full_pipeline_evaluation\test_worker_integration.py
```

These test commands are model-free and bounded. Focused files finish in
seconds; the broad enrollment matrix can take several minutes. They do not
materialize the 30/60-minute WAV set and do not start the scientific campaign.

The tests verify restart-safe prepare, H2-only membership, a truthful bounded
evidence-audit run, development-only promotion, the post-freeze
selected-tuning held-out overlay, speaker-conservative FPIR calibration,
truth-free causal transitions, calibration-assignment checksums, and
deterministic hierarchical bootstrap.
