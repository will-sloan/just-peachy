# Hybrid speaker-attribution evaluation

## Scientific purpose and scope

This additive Stage 12-style framework answers whether a selected anonymous
diarization system and selected open-set speaker-recognition system jointly
produce correct persistent identities. It reuses the exact controlled
diarization benchmark `controlled_diarization_v1_acd5e6e431d8` and its existing
waveforms. The hybrid protocol adds metadata only.

The framework does not change ASR, training, Phase-4 identities, source audio,
controlled recipes, diarization references, or anonymous DER/JER. It does not
use transcript content. Output turns reserve `text` and `asr_status` fields for
later integrated evaluation, but ASR is never run here.

## Frozen dependency chain

Scientific execution is intentionally gated:

1. The Common Voice speaker-breadth protocol supplies speaker-disjoint source
   speakers and reserved enrollment clips.
2. The speaker backend finalist and enrollment/live-duration policy must be
   selected outside this layer.
3. Controlled diarization development must select and freeze its pipeline
   configuration.
4. Hybrid development may compare only the small declared decision-policy grid.
5. An operator reviews development output and freezes one complete hybrid
   configuration with a rationale.
6. Evaluation accepts only the matching frozen hybrid and diarization hashes.
   Evaluation-side threshold or policy overrides are rejected.

No scientific readiness is implied by the included engineering smoke policy.

## Exact repository and external paths

| Item | Path or identity |
|---|---|
| Controlled benchmark | `benchmarks/stage11/controlled_diarization_v1` |
| Controlled benchmark ID | `controlled_diarization_v1_acd5e6e431d8` |
| Hybrid selection config | `configs/automated_evaluation/hybrid_speaker_attribution.v1.yaml` |
| Frozen hybrid protocol | `benchmarks/hybrid_speaker_attribution/hybrid_speaker_attribution_v1` |
| Hybrid protocol ID | `hybrid_speaker_attribution_v1_6c43a2bbe1ca` |
| Controlled audio | `%JP_GENERATED_DATA_ROOT%/controlled_diarization_v1`, or `%USERPROFILE%/JustPeachyGeneratedData/controlled_diarization_v1` |
| Reserved enrollment audio | logical paths below `%JP_DATA_ROOT%`, normally `Raw Datasets (Not formatted)/Common Voice/...` |
| Controlled results | operator `-DiarizationResultRoot` |
| Hybrid results | operator `-ResultRoot`, default `%USERPROFILE%/JustPeachyResults/hybrid_speaker_attribution` |
| Compact summaries | operator `-CollectRoot`, normally `%USERPROFILE%/JustPeachyResearchSummaries/...` |

The hybrid protocol contains 564 overlay units and 960 unique reserved
enrollment clips. Development/evaluation source-speaker intersection and
enrollment/mixture source-clip intersection are both zero.

## Identity overlays

Every controlled case receives exactly three overlays without a waveform copy:

- `ALL_KNOWN`: all case speakers have exact tier-scoped enrolled IDs.
- `MIXED_KNOWN_UNKNOWN`: the frozen source overlay determines which case
  speakers are enrolled and which are strangers.
- `ALL_UNKNOWN`: all case speakers are strangers; deterministic background
  impostor enrollments keep this a real open-set search rather than an empty DB.

Stable IDs are `ENROLLED_<TIER>_NNNN` for enrolled speakers and
`UNKNOWN_REFERENCE_<TIER>_NNNN` for unknown references. The latter are scoring
identities only and are never exposed to the model.

At runtime, predicted diarization clusters receive `Unknown_1`, `Unknown_2`,
and so on in first-appearance order within one recording. The same cluster
retains the same unknown label after silence or re-entry. Labels are not global
across recordings.

## Enrollment and embedding cache

`hybrid-enrollment-policy.v1` declares the exact backend ID, source enrollment
study, count of distinct reserved clips, enrollment aggregation, normalization,
cosine scoring threshold, segment/evidence minima, and evaluation-tuning ban.
The policy is runtime-selectable but must match the selected backend.

The selected speaker backend is loaded once per extraction worker. Cached
observations bind the audio SHA-256, interval, role, and job identity. The
physical local path and scoring threshold do not affect the job identity.
Therefore path rebasing remains portable and threshold/margin exploration
reuses embeddings. Failed and too-short observations remain explicit.

Internal embeddings from a diarizer are not silently compared with enrollment
templates. The hybrid layer extracts both enrollment and diarized-segment
embeddings through the explicitly selected speaker backend. A shared model is
possible only when the selected diarization pipeline and identity backend
actually name the same qualified component.

## Final and progressive attribution

Final/offline mode aggregates all eligible evidence from one anonymous cluster.
Progressive mode processes diarized segments in time order and recomputes a
decision from the prefix seen at that moment. No later segment, reference
identity, or final cluster decision is visible to an earlier progressive row.

Evidence states are:

- `PROVISIONAL` / `INSUFFICIENT_EVIDENCE` below the minimum evidence duration;
- `KNOWN` when top cosine score meets the frozen threshold and optional margin;
- `UNKNOWN` / `OPEN_SET_REJECTION` otherwise.

Evidence checkpoints are 0.5, 0.75, 1, 1.5, 2, 3, and 5 seconds. Whole
eligible segments are accumulated in chronological order. The result records
the realized duration, candidate scores, observed margin, frozen threshold,
and assigned state. Optional predicted-overlap exclusion is a frozen policy;
the default includes predicted overlapping segments.

## Scoring rules and metric fields

Known IDs are exact strings. Unknown references alone receive an optimal
recording-local permutation mapping to `Unknown_N`; this makes unknown scoring
label-permutation invariant. The mapping does not rename known identities,
split a merged cluster, combine fragmented clusters, or feed back into model
decisions.

Primary metric fields are:

- `known_identity_accuracy`: correctly named known-speaker overlap time divided
  by known reference speaker-time.
- `wrong_known_rate`: time assigned to the wrong enrolled name divided by known
  reference speaker-time.
- `known_to_unknown_rate`: known time rejected or still provisional divided by
  known reference speaker-time.
- `unknown_rejection_rate`: unknown time assigned to its optimally mapped
  persistent `Unknown_N` divided by unknown reference speaker-time.
- `false_known_rate`: unknown time assigned any enrolled identity divided by
  unknown reference speaker-time.
- `identity_coverage`: reference speaker-time overlapped by any attributed
  prediction divided by reference speaker-time.
- `identity_precision_on_covered_time`: correctly attributed time divided by
  covered time.
- `time_weighted_identity_accuracy`: correctly attributed known and mapped
  unknown time divided by all reference speaker-time.
- `progressive_time_weighted_identity_accuracy` and
  `progressive_false_known_rate`: causal equivalents.
- `identity_churn_count`: label transitions over successive observations of one
  anonymous cluster.
- `stable_known_identity_latency_mean_sec`: mean delay from a known speaker's
  first reference onset to its first progressive exact-name decision.
- `fragmentation_count`: excess predicted clusters overlapping each reference
  speaker.
- `merge_count`: excess reference speakers overlapping each predicted cluster.
- `reference_speaker_count`, `predicted_cluster_count`, and `valid_output`.

Raw duration decompositions include `known_correct_time_sec`,
`wrong_known_time_sec`, `known_rejected_as_unknown_time_sec`,
`unknown_correctly_rejected_time_sec`, `unknown_rejected_wrong_instance_time_sec`,
`false_known_time_sec`, `covered_time_sec`, and
`reference_speaker_time_sec`.

Each result also carries the controlled anonymous diarization summary unchanged
and an oracle-diarization identity diagnostic. This separates identity-model
error from diarization miss, false alarm, confusion, fragmentation and merge.
Error-event output predeclares:

`DIARIZATION_MISS`, `DIARIZATION_FALSE_ALARM`, `DIARIZATION_CONFUSION`,
`DIARIZATION_FRAGMENTATION`, `DIARIZATION_MERGE`, `KNOWN_CORRECT`,
`WRONG_KNOWN`, `REJECTED_AS_UNKNOWN`, `UNKNOWN_CORRECTLY_REJECTED`,
`FALSE_KNOWN`, `INSUFFICIENT_EVIDENCE`, and `IDENTITY_CHURN`.

## Result contract and restart behavior

Each valid case/overlay result contains:

- `run.json`, `configuration_identity.json`, `diarization_identity.json`,
  `speaker_backend_identity.json`, `enrollment_identity.json`;
- final cluster, progressive turn, evidence checkpoint and future-ASR JSONL;
- reference turns, metric summary, error events, oracle diagnostic;
- resource usage and a validated checksum manifest.

A complete matching result is `REUSE`. An invalid existing destination is moved
under `_partial` before a new atomic staging result is published. Per-case
failure records live under `_failed`; a queue with failures exits as failed.

## Analysis and collection

The analysis manifest binds the exact configuration IDs and validated unit
count. The primary files are:

`overall_results.csv`, `recording_results.csv`, `overlay_results.csv`,
`known_identity_results.csv`, `unknown_identity_results.csv`,
`false_known_results.csv`, `identity_latency_results.csv`,
`identity_churn_results.csv`, `reentry_results.csv`,
`fragmentation_merge_results.csv`, `speaker_count_results.csv`,
`turn_cadence_results.csv`, `overlap_results.csv`,
`time_weighted_results.csv`, `oracle_diagnostics.csv`,
`resource_results.csv`, `reliability_summary.csv`, and `report.md`.

Development additionally writes `development_overall.csv`,
`threshold_curve.csv`, `evidence_duration_curve.csv`, and
`margin_analysis.csv`. Confidence intervals use a recording-level bootstrap
with seed 3800, 500 repetitions, and 95% limits. Analysis is read-only.
The threshold curve always includes the product-policy threshold plus up to 21
deterministic development-score quantiles labelled
`hybrid_development_candidate`; margin rows compare the declared 0.00 and 0.05
options. These are decision material, not an automatic winner. Evaluation
analysis never creates or applies a new threshold.

`Collect` copies only compact analysis, protocol, and frozen-configuration
artifacts. It declares that audio, models, and embedding caches are excluded.

## Runner actions

Use `scripts/run_hybrid_speaker_attribution.ps1`:

- `Audit`: no inference; checks protocol, enrollment files, selections, assets,
  and environment availability.
- `Prepare`: metadata-only protocol generation/reuse.
- `Validate`: hashes and scientific split/leakage contracts; optionally hashes
  all external enrollment files.
- `Plan`: no inference; reports cases, overlays, reusable diarization and
  embedding workload.
- `Smoke`: defaults to one controlled smoke case and all three overlays; marked
  non-scientific through its required policy.
- `RunDevelopment`: runs only development and stops at completion.
- `AnalyzeDevelopment`: writes development decision material.
- `Freeze`: records an operator-selected complete configuration and rationale.
  `DevelopmentConfigurationId` identifies the validated source result set; the
  frozen file separately records the selected configuration ID after applying
  an operator-chosen development-only threshold or margin.
- `RunEvaluation`: requires matching frozen hybrid and diarization configs;
  rejects ad hoc tuning fields.
- `Status`, `Analyze`, and `Collect`: validate status, aggregate results, and
  create a compact handoff.

The exact setup and commands are also in `app/hybrid_speaker_attribution/README.md`.
