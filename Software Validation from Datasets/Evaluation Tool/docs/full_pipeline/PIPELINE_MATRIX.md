# Just-Peachy Full Speech-Pipeline Matrix V1

## Purpose and authority

This document is the readable companion to
`configs/automated_evaluation/full_pipeline_matrix.v1.yaml`. The YAML is the
machine-readable authority. This document explains the same locked 18-pipeline
program, its tier rules, policy bindings, selection procedure, and existing
research anchors.

- Program identity: `just_peachy_full_pipeline_program_v1`
- Protocol: `full_pipeline_protocol.v1`
- Schema: `just-peachy-full-pipeline-matrix.v1`
- Status: `SPECIFICATION_LOCKED_NO_SCIENTIFIC_CAMPAIGN_STARTED`
- Matrix cardinality: **18 = 2 ASR x 3 anonymous diarization x 3 identity**
- Scientific seed: `3800`
- Audio sample rate: `16000 Hz`

The hybrid labels are annotations on diarization-plus-identity combinations.
They are not another matrix axis. H2, H4, and H5 therefore identify six Tier-B
pipelines after the two ASR choices are applied, not an additional multiplier.

## Axis aliases

| Alias | Axis | Exact component or pipeline | Current qualification/evidence state |
|---|---|---|---|
| AO | ASR | `sherpa_onnx` | Qualified; native replay still requires binding to the full-pipeline streaming contract. |
| AG | ASR | `sherpa_onnx_libri_giga_zipformer_2023_06_21` | Qualified under the segment contract; upstream is native-streaming capable, but the current large-study guard blocks claiming that segment result as native-streaming evidence. |
| DW | Anonymous diarization | `modular_pyannote_wespeaker` | Held-out standalone primary. |
| DR | Anonymous diarization | `modular_pyannote_redimnet2` | Held-out standalone efficiency fallback. |
| DE | Anonymous diarization | `modular_pyannote_speechbrain_ecapa` | Development-nondominated comparator; not held out and carries a speaker-confusion safeguard warning. |
| IW | Enrolled identity | `wespeaker` | Qualified with warnings; 256-dimensional, minimum duration 0.75 s. |
| IR | Enrolled identity | `redimnet2_b2_speaker_embedding` | Qualified; 192-dimensional, minimum duration 0.50 s. |
| IE | Enrolled identity | `speechbrain_ecapa` | Qualified on CPU; 192-dimensional, minimum duration 0.75 s. |

All three diarizers use the frozen Pyannote Segmentation 3.0 shared-cache
identity and the same `1.5 s` window, `0.75 s` step, estimated speaker count,
agglomerative-cosine clustering family, and `0.35` clustering threshold. Their
embedding backend is the distinguishing anonymous-diarization component.

## Hybrid-label map

| Label | Anonymous diarization | Identity | Evidence status |
|---|---|---|---|
| H1 | DW | IW | Development comparator |
| H2 | DR | IR | Frozen hybrid anchor |
| H3 | DR | IW | Development comparator |
| H4 | DW | IR | Frozen hybrid anchor |
| H5 | DR | IE | Frozen hybrid anchor |
| H6 | DW | IE | Development comparator |
| C7 | DE | IW | New challenger; logical label only, not registered or frozen in the completed hybrid protocol |
| C8 | DE | IR | New challenger; logical label only, not registered or frozen in the completed hybrid protocol |
| C9 | DE | IE | New challenger; logical label only, not registered or frozen in the completed hybrid protocol |

## Complete 18-pipeline matrix

Every row is mandatory in Tier A. `Required` in the Tier-B column means the row
is one of the six unconditional extended pipelines. `Gate` means it can enter
Tier B only under the development-only challenger rule; at most two such rows
may be added across the entire matrix.

| Pipeline ID | ASR | Anonymous diarization | Identity | Hybrid label | Enrollment policy | Frozen anchor | Tier B |
|---|---|---|---|---|---|---|---|
| `fullpipe_v1_ao_dw_iw` | AO | DW | IW | H1 | `hybrid_product_v2_wespeaker_scientific_v1` | No | Gate |
| `fullpipe_v1_ao_dw_ir` | AO | DW | IR | H4 | `hybrid_product_v2_redimnet2_scientific_v1` | Yes | Required |
| `fullpipe_v1_ao_dw_ie` | AO | DW | IE | H6 | `hybrid_product_v2_speechbrain_ecapa_scientific_v1` | No | Gate |
| `fullpipe_v1_ao_dr_iw` | AO | DR | IW | H3 | `hybrid_product_v2_wespeaker_scientific_v1` | No | Gate |
| `fullpipe_v1_ao_dr_ir` | AO | DR | IR | H2 | `hybrid_product_v2_redimnet2_scientific_v1` | Yes | Required |
| `fullpipe_v1_ao_dr_ie` | AO | DR | IE | H5 | `hybrid_product_v2_speechbrain_ecapa_scientific_v1` | Yes | Required |
| `fullpipe_v1_ao_de_iw` | AO | DE | IW | C7 | `hybrid_product_v2_wespeaker_scientific_v1` | No | Gate |
| `fullpipe_v1_ao_de_ir` | AO | DE | IR | C8 | `hybrid_product_v2_redimnet2_scientific_v1` | No | Gate |
| `fullpipe_v1_ao_de_ie` | AO | DE | IE | C9 | `hybrid_product_v2_speechbrain_ecapa_scientific_v1` | No | Gate |
| `fullpipe_v1_ag_dw_iw` | AG | DW | IW | H1 | `hybrid_product_v2_wespeaker_scientific_v1` | No | Gate |
| `fullpipe_v1_ag_dw_ir` | AG | DW | IR | H4 | `hybrid_product_v2_redimnet2_scientific_v1` | Yes | Required |
| `fullpipe_v1_ag_dw_ie` | AG | DW | IE | H6 | `hybrid_product_v2_speechbrain_ecapa_scientific_v1` | No | Gate |
| `fullpipe_v1_ag_dr_iw` | AG | DR | IW | H3 | `hybrid_product_v2_wespeaker_scientific_v1` | No | Gate |
| `fullpipe_v1_ag_dr_ir` | AG | DR | IR | H2 | `hybrid_product_v2_redimnet2_scientific_v1` | Yes | Required |
| `fullpipe_v1_ag_dr_ie` | AG | DR | IE | H5 | `hybrid_product_v2_speechbrain_ecapa_scientific_v1` | Yes | Required |
| `fullpipe_v1_ag_de_iw` | AG | DE | IW | C7 | `hybrid_product_v2_wespeaker_scientific_v1` | No | Gate |
| `fullpipe_v1_ag_de_ir` | AG | DE | IR | C8 | `hybrid_product_v2_redimnet2_scientific_v1` | No | Gate |
| `fullpipe_v1_ag_de_ie` | AG | DE | IE | C9 | `hybrid_product_v2_speechbrain_ecapa_scientific_v1` | No | Gate |

All 18 rows additionally bind:

- hybrid decision policy `full_pipeline_open_set_decision.v1`;
- streaming policy `full_pipeline_incremental_stream.v1`;
- protocol `full_pipeline_protocol.v1`;
- sample rate `16000 Hz` and seed `3800`;
- no implicit model download during evaluation.

## Pipeline-ID and policy-version semantics

The stable human ID pattern is:

```text
fullpipe_v1_{asr alias}_{anonymous-diarization alias}_{identity alias}
```

For example, `fullpipe_v1_ag_dr_ie` means AG ASR, DR anonymous
diarization, and IE enrolled identity. `fullpipe_v1` binds all of the
following, even though the short ID does not spell them out:

- `full_pipeline_protocol.v1`;
- the row's identity-specific enrollment policy and its SHA-256;
- `full_pipeline_open_set_decision.v1`;
- `full_pipeline_incremental_stream.v1`;
- the exact component, asset, configuration, and environment identities in the
  authoritative YAML and its source registries.

Every result must repeat those identities explicitly. A result-affecting change
to a model, asset, enrollment rule, threshold policy, streaming policy, or
protocol requires a new protocol version and pipeline identity. A physical
asset-path relocation does not change a scientific identity when its logical
path and verified content hash remain unchanged.

The frozen hybrid-anchor thresholds recorded on H2/H4/H5-derived rows are
historical development-policy anchors:

| Anchor | Score threshold | Margin | Minimum evidence | Enrollment aggregation |
|---|---:|---:|---:|---|
| H2 | `0.5265351286789879` | `0.03` | `2.0 s` | `multi_template_max` |
| H4 | `0.5331755752703802` | `0.03` | `2.0 s` | `multi_template_max` |
| H5 | `0.4572960706169966` | `0.03` | `2.0 s` | `multi_template_top2_mean` |

They are not universal or Beaker production thresholds. The V1 full-pipeline
decision policy recalibrates on development only, freezes before evaluation,
and binds the resulting threshold to the exact pipeline and realized gallery
size. Evaluation recalibration is prohibited.

## Shared enrollment, open-set, and streaming policies

The enrollment policies use three utterances targeting about 10 seconds total.
IW and IE use multi-template top-two-mean aggregation; IR uses multi-template
maximum aggregation. The policy identity, file, and hash in the YAML are part
of each pipeline identity.

`full_pipeline_open_set_decision.v1` declares:

- raw scores are cosine similarities, not probabilities;
- pairwise-verification thresholds are not production identity thresholds;
- calibration uses the maximum gallery score and a required Top-1 minus Top-2
  margin for each pipeline and realized gallery size;
- target FPIR operating points are 0.5%, 1%, 2%, and 5%;
- the first label is `Unknown_1`, with stable session-local `Unknown_N` labels;
- identity state is `unknown`, `tentative`, or `confirmed`;
- minimum evidence is 2.0 seconds and minimum embedding consistency is 0.35;
- confirmation requires two consecutive passes with 0.02 hysteresis;
- identity expires after 120 seconds;
- predicted overlap is excluded from primary identity evidence and retained as
  a diagnostic;
- cluster evidence uses a duration-weighted normalized mean.

`full_pipeline_incremental_stream.v1` declares deterministic 100 ms chunks,
500 ms updates, a per-record reset, backend-default endpointing, a required
source clock, and preservation of partial/final ASR events plus transcript and
identity revisions. Scientific file simulation is not real-time paced. Live
microphone mode is a product/runtime mode and cannot be substituted for the
controlled scientific source clock.

## Evaluation tiers

### Tier A — all 18

Every matrix row receives all of the following under common contracts:

1. Adapter qualification.
2. End-to-end smoke.
3. Controlled development.
4. Untouched held-out controlled evaluation.
5. Common metrics.
6. Common result schema.

Tier A is not optional screening of a convenient subset. Failures, invalid
outputs, and missing items remain visible in the denominator and result record.

### Tier B — extended pipelines

The six unconditional Tier-B rows are:

```text
fullpipe_v1_ao_dr_ir   # AO-H2
fullpipe_v1_ag_dr_ir   # AG-H2
fullpipe_v1_ao_dw_ir   # AO-H4
fullpipe_v1_ag_dw_ir   # AG-H4
fullpipe_v1_ao_dr_ie   # AO-H5
fullpipe_v1_ag_dr_ie   # AG-H5
```

At most two additional Tier-A pipelines may enter Tier B. An addition must show
a distinct non-dominated position using development evidence only. It cannot be
promoted because of held-out evaluation inspection, label preference, or a
single favorable metric. The six required rows remain required regardless of
whether challengers qualify.

C7, C8, and C9 are not preapproved Tier-B additions. They first need registered,
frozen development policies and valid development full-pipeline evidence.

### Tier C — production candidates

Tier C may contain at most three pipelines, selected only after held-out and
extended testing. Its intended roles are:

1. Primary safety/accuracy architecture.
2. Efficiency/fallback architecture.
3. Provenance-safe or scientifically distinct alternative.

`current_selection` is deliberately empty. Prompt 0 does not select Tier C, and
historical component or hybrid winners must not be relabelled as complete
speech-pipeline winners before ASR, streaming, attribution, and reliability are
measured together.

## Selection policy

Selection uses `full_pipeline_constraint_pareto_selection.v1`. It uses
constraints, ordered priorities, and Pareto reasoning. It does **not** use an
opaque weighted score.

A pipeline must first satisfy the reliability constraints:

- valid common contracts and checksums;
- held-out evaluation untouched by development calibration;
- failures and missing items retained in denominators;
- no reference-transcript or reference-speaker fallback;
- real-time operation and restart reliability reported.

Remaining pipelines are considered in this exact priority order:

| Priority | Criterion | Direction |
|---:|---|---|
| 1 | Wrong-known speaker time | Minimize |
| 2 | Stranger false-known time | Minimize |
| 3 | Premature wrong-name exposure | Minimize |
| 4 | Speaker-attributed word errors | Minimize |
| 5 | Correctly named known-speaker time | Maximize |
| 6 | Anonymous-speaker confusion and cluster contamination | Minimize |
| 7 | Time to first readable text | Minimize |
| 8 | Time to stable transcript | Minimize |
| 9 | Time to stable correct speaker name | Minimize |
| 10 | Transcript and identity revisions | Minimize |
| 11 | Real-time operation and reliability | Maintain |
| 12 | CPU, RAM, and model complexity | Minimize only among scientifically comparable systems |

Technical ranking and licensing/provenance deployment ranking are separate.
A technically strong system can remain ineligible for production. In
particular, AG must not be called commercially cleared while the GigaSpeech
training-provenance review remains unresolved. Repository redistribution also
remains unresolved while the repository has no project-level license file.

## Current evidence anchors

The matrix is grounded in these immutable source anchors, relative to the
Evaluation Tool root:

| Evidence | Path | SHA-256 or protocol identity |
|---|---|---|
| Component registry | `configs/automated_evaluation/component_registry.v1.yaml` | `f0d265fa7d983bda65c50633e2c16430048933a617f8f202292e0b7a12dfc9a9` |
| Model-asset registry | `configs/automated_evaluation/model_asset_registry.v1.yaml` | `89bf1697eccbc133618a9e846b3179d247f89251a238a400116e7a5c27badc0c` |
| Environment registry | `configs/automated_evaluation/environment_profiles.stage8.v1.yaml` | `32b08de6e9971df54e2b14e1be8133d0be7ea663620e2294f2668ff99127e851` |
| Frozen diarization development selection | `JustPeachyResults/diarization_product_v2_development/frozen_diarization_development_selection.yaml` | `a6191598972959b9f503da17e2b07832083021c76bad285e0901c12ac2c677cd` |
| Frozen hybrid development selection | `JustPeachyResults/hybrid_speaker_attribution_product_v2_development/frozen_hybrid_product_v2_selection.yaml` | `2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a` |
| Frozen final hybrid selection | `JustPeachyResults/hybrid_speaker_attribution_product_v2_final_evaluation/final_hybrid_product_v2_selection.yaml` | `1629977f026159f9cd5ce0064a04cb811dc3f08cca62458b7eb12308a45560d2` |

The most relevant completed scientific result roots are:

| Study | Result root | Protocol/evidence identity | Current conclusion |
|---|---|---|---|
| Common Voice 60+ ASR | `JustPeachyResults/asr_commonvoice/commonvoice_60plus_asr_v1/campaign_commonvoice_60plus_asr_v1_10a3c45df81c` | `commonvoice_60plus_asr_v1_fb22c247f5f7` | AG WER 9.30% versus AO 15.36% on this read-speech panel; not a native-streaming or deployment-clearance result. |
| Speaker deployment replay | `JustPeachyResults/speaker_embedding_deployment/speaker_embedding_deployment_v1_4779270a5bf0` | `speaker_embedding_deployment_v1_4779270a5bf0` | WeSpeaker was the standalone 272-person accuracy-first recommendation; open-set gallery calibration was essential. |
| Enrollment/live-duration study | `JustPeachyResults/speaker_enrollment/speaker_enrollment_live_v2_5107db9ab304` | `speaker_enrollment_live_v2_5107db9ab304` | WeSpeaker accuracy-first, IR compact fallback, IE speed/accuracy alternative; real Beaker calibration still required. |
| Final standalone diarization | `JustPeachyResults/diarization_finalists_final_evaluation` | `controlled_diarization_v1_acd5e6e431d8`; `diarization_product_v2_6b6c50a5de31` | DW primary, DR efficiency fallback; DE not held out. |
| Final hybrid attribution | `JustPeachyResults/hybrid_speaker_attribution_product_v2_final_evaluation` | `hybrid_speaker_attribution_product_v2_a68cc1ac26aa` | H5 held-out primary; H2 fallback; H4 evaluated reference. Readiness still requires policy work and real Beaker data. |

The final held-out hybrid anchor comparison was:

| Anchor | Correctly named known time | Wrong-known time | Stranger false-known time | Stable-name latency | Desktop RTF | Historical disposition |
|---|---:|---:|---:|---:|---:|---|
| H5 (DR + IE) | 62.35% | 1.42% | 1.35% | 7.417 s | 0.492 | Final hybrid primary |
| H2 (DR + IR) | 62.76% | 1.70% | 1.80% | 7.442 s | 0.507 | Final hybrid fallback; same-model simplicity |
| H4 (DW + IR) | 62.89% | 1.61% | 1.62% | 7.906 s | 0.759 | Evaluated accuracy/reference architecture, not in final selected IDs |

These values justify retaining H2/H4/H5 as Tier-B anchors. They do not select an
ASR-hybrid full pipeline, because the hybrid study did not run ASR or measure
speaker-attributed word errors, partial transcript timing, or revision behavior.

## Explicit gaps and guards

- **C7-C9 are logical challenger labels only.** They have no completed hybrid
  combination registration, frozen scientific decision thresholds, or held-out
  hybrid result. Their rows exist so Tier A can test the declared 3 x 3 speaker
  matrix; they are not frozen anchors.
- **DE has no held-out standalone evidence.** It was development-nondominated but
  was rejected from the standalone final on a clear speaker-confusion safeguard
  regression. No C7-C9 advancement may assume that issue is resolved.
- **AG native streaming is guarded.** The upstream checkpoint is
  native-streaming capable, but the completed large comparison used the current
  segment contract. `BLOCKED_BY_CURRENT_LARGE_STUDY_SEGMENT_CONTRACT_GUARD`
  remains authoritative until the full-pipeline native binding is qualified.
- **AO also needs full-pipeline binding.** Existing adapter replay support is not
  evidence that the complete AO pipeline satisfies V1 partial-event, source-clock,
  endpoint, and revision contracts.
- **There is no Tier-C selection.** Historical H5/H2 and AG/AO evidence informs
  program design but cannot replace the required held-out, extended, end-to-end
  selection.
- **No completed study combines ASR, anonymous diarization, enrolled identity,
  open-set decisions, and incremental transcript revisions.** Speaker-attributed
  WER and the three text/name latency objectives remain unmeasured jointly.
- **Real-device evidence is absent.** Existing controlled work uses prompted/read
  speech and synthetic placement or causal replay. Final thresholds, true live
  latency, power, and Beaker acoustics require a disjoint real-device calibration
  and evaluation program.
- **AG deployment provenance is unresolved.** Technical results must remain
  separate from the commercial-deployment review of GigaSpeech training
  provenance.
- **IE asset freezing has a recorded provenance discrepancy.** The local
  five-file cache is broader than the frozen two-file identity, and the audited
  cache records `label_encoder.ckpt` while the hyperparameters refer to
  `label_encoder.txt`. Completed extraction is valid, but redistribution or a
  production asset freeze requires resolution.
- **Pyannote acquisition is gated.** The installed Segmentation 3.0 asset is
  frozen for local scientific use, but it must not be redistributed without the
  separate gated-asset review.

Until these gaps are resolved, the correct state is a locked evaluation program,
not a production architecture decision.
