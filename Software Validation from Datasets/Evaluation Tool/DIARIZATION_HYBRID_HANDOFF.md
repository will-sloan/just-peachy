# Just-Peachy Diarization and Hybrid Speaker Attribution Handoff

Snapshot date: 2026-08-21 (America/Toronto)  
Repository: `C:\Users\amiri\Documents\GitHub\just-peachy`  
Evaluation tool: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool`  
Git commit at audit time: `2902ce9b98efedd63ccbc88b47645097b339585f`

> Important: this handoff describes the current working tree, which contains
> uncommitted diarization/hybrid changes. It is not a claim that every described
> behavior exists in the commit named above. Preserve the working tree and inspect
> `git diff` before editing any of the files listed here.

## 1. Executive state

Just-Peachy currently has three related but distinct research layers:

1. **Controlled diarization benchmark** — asks *which anonymous speaker spoke
   when?* on deterministic, synthetically arranged conversations made from real
   Common Voice recordings.
2. **Native-condition Stage 11 evaluation** — asks the same anonymous
   diarization question on AMI, CHiME-6, and, where the references permit it,
   VOiCES.
3. **Hybrid speaker attribution** — consumes controlled diarization output plus
   an independently selected speaker-embedding/enrollment policy and asks
   whether each anonymous cluster should be assigned an exact enrolled identity
   or a recording-local persistent `Unknown_N` label.

These layers must not be conflated:

```text
Audio
  -> diarization: anonymous SPEAKER_00 / SPEAKER_01 + time intervals
  -> speaker attribution: known person ID or Unknown_N for each cluster
  -> optional future ASR: text attached to attributed intervals
```

Current scientific status:

| Layer | Prepared/validated | Inference evidence now present | Frozen scientific decision | Full evaluation complete |
|---|---:|---|---:|---:|
| Controlled benchmark | Yes | One non-scientific Sherpa smoke case | No | No |
| Native Stage 11 | Yes | One very short Sherpa AMI smoke unit | N/A for a campaign | No |
| Hybrid attribution | Protocol is valid | No hybrid result root/results | No | No |

The repository therefore contains a substantial evaluation framework, not a
completed diarization model comparison. Do not use the existing one-case smoke
numbers to select a production model.

## 2. Vocabulary and scientific boundaries

### Diarization

Diarization produces anonymous, time-aligned speaker segments. It normally has
four stages:

```text
speech segmentation/VAD
  -> speaker embeddings for speech windows
  -> clustering of similar windows
  -> timestamped anonymous labels (RTTM)
```

It does **not** establish a real-world identity. A perfect diarizer may call a
person `SPEAKER_02`; that is still anonymous.

### Speaker embedding and enrollment

A speaker embedding represents voice characteristics. Enrollment aggregates one
or more recordings into a template for a known identity. The enrollment/live
study chooses the embedding backend, enrollment aggregation, score threshold,
margin, and minimum evidence requirements. That decision belongs outside the
hybrid evaluator.

### Hybrid attribution

Hybrid attribution re-embeds diarized segments using the selected speaker
backend, compares them with enrolled templates, and makes an open-set decision:

```text
anonymous diarization cluster
  -> evidence aggregation
  -> Top-1 known candidate + score
  -> Top-2 score / margin
  -> threshold + margin + evidence policy
  -> exact known ID OR Unknown_N
```

The hybrid layer does not tune the embedding network, alter the diarization
labels, or run ASR. Its transcript rows intentionally have `text: null` and
`asr_status: NOT_RUN`.

## 3. Important paths

All paths below are relative to the Evaluation Tool unless an absolute path is
shown.

### Primary entry points

| Purpose | Path |
|---|---|
| Unified Python launcher | `run_evaluation.py` |
| Controlled PowerShell wrapper | `scripts/run_controlled_diarization.ps1` |
| Hybrid PowerShell wrapper | `scripts/run_hybrid_speaker_attribution.ps1` |
| Controlled implementation | `app/controlled_diarization/` |
| Native Stage 11 implementation | `app/diarization_evaluation/` |
| Hybrid implementation | `app/hybrid_speaker_attribution/` |

### Protocols and configuration

| Purpose | Path |
|---|---|
| Controlled design + pipeline registry | `configs/automated_evaluation/controlled_diarization_benchmark.v1.yaml` |
| Native Stage 11 policy | `configs/automated_evaluation/diarization_evaluation.v1.yaml` |
| Native artifact registry | `configs/automated_evaluation/diarization_artifact_registry.v1.yaml` |
| Hybrid design grid | `configs/automated_evaluation/hybrid_speaker_attribution.v1.yaml` |
| Non-scientific hybrid smoke policy | `configs/automated_evaluation/hybrid_enrollment_policy.non_scientific_smoke.yaml` |
| Component catalog | `configs/automated_evaluation/component_registry.v1.yaml` |
| Model assets and hashes | `configs/automated_evaluation/model_asset_registry.v1.yaml` |
| Environment definitions | `configs/automated_evaluation/environment_profiles.stage8.v1.yaml` |
| Individual diarization configs | `configs/inference/components/diarization/` |

### Frozen/generated inputs and result roots

| Content | Default path |
|---|---|
| Controlled protocol metadata | `benchmarks/stage11/controlled_diarization_v1/` |
| Controlled generated WAVs | `JustPeachyGeneratedData/controlled_diarization_v1/` |
| Controlled diarization results | `JustPeachyResults/diarization/controlled_diarization_v1/` |
| Native manifests | `benchmarks/stage11/{small,standard,large}/` |
| Native per-unit results | `runs/diarization_evaluation/` |
| Hybrid protocol | `benchmarks/hybrid_speaker_attribution/hybrid_speaker_attribution_v1/` |
| Hybrid results | `JustPeachyResults/hybrid_speaker_attribution/` |
| Human/research summaries | `JustPeachyResearchSummaries/` |

The controlled generated-data root can be relocated with
`JP_GENERATED_DATA_ROOT`. The controlled result root can be relocated with
`JP_DIARIZATION_RESULT_ROOT`. The wrappers append
`controlled_diarization_v1` to those base roots. Raw/generated audio and model
assets must remain outside Git.

### Detailed documentation

- `app/controlled_diarization/README.md`
- `app/diarization_evaluation/README.md`
- `app/hybrid_speaker_attribution/README.md`
- `docs/automated_evaluation/controlled_diarization_benchmark.md`
- `docs/automated_evaluation/stage_11_diarization.md`
- `docs/automated_evaluation/hybrid_speaker_attribution.md`
- `docs/automated_evaluation/speaker_diarization_stack_readiness.md`

The readiness document is the best source for exact model filenames, hashes,
licenses, acquisition routes, and isolated environment details.

## 4. Existing diarization models and pipelines

### Pipelines registered in the controlled benchmark

| Pipeline ID | Segmentation | Embedding/clustering | Environment | Current role/status |
|---|---|---|---|---|
| `sherpa_onnx_diarization` | Sherpa internal pyannote Segmentation 3.0 ONNX | ERes2Net Base ONNX + Sherpa FastClustering; current threshold 0.5 | `.stage8-envs/onnx` | Complete pipeline; `STAGE11_AUTHORIZED` |
| `modular_energy_campplus` | Lightweight energy VAD windows | CAM++ + deterministic average-link cosine clustering; current threshold 0.5 | `.stage8-envs/onnx` | Software qualified; development calibration required |
| `modular_pyannote_campplus` | pyannote Segmentation 3.0 | CAM++ + deterministic average-link cosine clustering; current threshold 0.5 | `.stage8-envs/credential-diarization` | Software qualified; development calibration required |
| `modular_energy_wespeaker` | Lightweight energy VAD windows | Stage 10 WeSpeaker ResNet221-LM + deterministic clustering; current threshold 0.5 | `.stage8-envs/wespeaker` | Software qualified; development calibration required |
| `pyannote_community1` | Community-1 internal PyanNet | Internal WeSpeaker ResNet34-LM + PLDA/VBx | `.stage8-envs/credential-diarization` | Software qualified, off-the-shelf/default comparison only |
| `oracle_turn_campplus_diagnostic` | Exact synthetic reference turns | CAM++ + deterministic clustering; threshold 0.55 | `.stage8-envs/onnx` | Diagnostic only; development and non-overlap cases only |
| `modular_pyannote_selected_embedding` | Intended pyannote segmentation | Final speaker embedding and clustering not selected | unresolved | Placeholder, `NOT_INTEGRATED` |

The thresholds shown above are engineering defaults. They are not production
identity thresholds and are not yet frozen scientific diarization decisions.

### Implemented component not in the controlled pipeline registry

`modular_pyannote_eres2net` has an inference component configuration and bounded
software-qualification evidence, but it is not currently listed in
`controlled_diarization_benchmark.v1.yaml`. Consequently, it is not a selectable
controlled-benchmark pipeline. A pyannote + ReDimNet2 path is also conceptually
possible, but no complete registered/frozen pipeline currently exists.

Adding either requires an explicit new pipeline entry, resolved environment and
asset identity, smoke qualification, development-only calibration, tests, and a
new frozen decision. Do not silently replace the implementation behind an
existing pipeline ID.

### Other declared native diarization backends

| Backend | Current repository state |
|---|---|
| `sherpa_onnx_diarization` | Qualified and the only backend authorized by the current frozen native Stage 11 registry. Run it in the ONNX environment. |
| `pyannote_community` | Local controlled software qualification exists, but the older native qualification registry still marks it `licence_action_required`/excluded. These two scopes are not interchangeable. |
| `picovoice_falcon` | Adapter/config exists; excluded because package, AccessKey, and licence acknowledgement are not present. |
| `nemo_diarization` | Adapter/config exists; excluded on this Windows profile. It requires its Linux/CUDA profile, configuration, and active checkpoints. |

Running native `status` from the core `.venv` may report Sherpa as unavailable
because that interpreter does not contain `sherpa_onnx`. That does not mean the
machine lacks it. The controlled status command resolves each pipeline's
isolated environment and is the more useful machine-wide readiness check.

### Asset/licence summary

- Sherpa-ONNX diarization/segmentation package: local ONNX assets; package/code
  licensing is recorded in the asset registry/readiness report.
- ERes2Net Base and CAM++ assets: Apache-2.0 provenance recorded by the project.
- WeSpeaker code: Apache-2.0; the official VoxCeleb weights used here are tracked
  as CC BY 4.0.
- pyannote Community-1: CC BY 4.0 with gated acquisition.
- pyannote Segmentation 3.0: MIT with gated acquisition.

No model binary should be committed. Inference disables implicit downloads;
assets must resolve through the registry and their expected hashes.

## 5. Controlled diarization benchmark

### Scientific purpose

This benchmark isolates diarization behavior across known factors while keeping
the audio construction deterministic. It uses real Common Voice 60+ voices but
arranges clips into synthetic conversations. It is best for controlled
comparisons of speaker count, cadence, overlap, segmentation, and clustering.
It is not evidence for spontaneous conversation, rooms, microphones, distance,
or device noise.

Protocol identity: `controlled_diarization_v1_acd5e6e431d8`  
Seed: `3800`  
Source protocol: `commonvoice_60plus_v1_27e72793b4c0`

### Frozen panel construction

- 192 unique source speakers.
- 3,528 unique mixture source clips.
- 960 reserved enrollment clips, disjoint from mixture clips.
- No exact source-clip reuse.
- Smoke: 12 speakers, 8 recordings; explicitly non-scientific.
- Development: 60 speakers, 60 recordings.
- Evaluation: 120 speakers, 120 recordings.
- Smoke, development, and evaluation speaker pools are disjoint.
- Evaluation assets are protected from future training use.
- Approximately 10,914.86 seconds / 3.03 hours of generated audio across 188
  WAV files (about 349 MB on the audited machine).

Factorial cells use:

- speaker count: 2, 3, 5, plus single-speaker controls;
- turn cadence: relaxed, standard, rapid;
- overlap: none, short-overlap/backchannel profile, moderate;
- 2 development replicates and 4 evaluation replicates per factorial cell;
- 60-second relaxed/standard sessions and 48-second rapid sessions, all within
  the configured 45–75 second bounds.

The reference is exact sample-placement timing from the generator. It is not a
human frame-level speech transcription. Twenty-seven recordings were selected
for human review, but all review statuses were `NOT_REVIEWED` at this snapshot.

### Scoring policies

Primary strict scoring:

- collar = 0 seconds;
- both overlap-aware and overlap-excluded scoring;
- estimated speaker count;
- scored UEM required.

Practical diagnostic scoring:

- collar = 0.25 seconds;
- both overlap modes;
- estimated speaker count;
- scored UEM required.

Per-case and aggregate outputs cover:

- DER and JER;
- missed speech, false alarm, and speaker confusion;
- reference/predicted speaker count, signed and absolute error, exact-count rate;
- speaker fragmentation/splits and merges;
- cluster purity and reference-speaker coverage;
- re-entry consistency and return/absence details;
- overlap-only behavior;
- boundary precision/recall/F1 at +/-250 ms and +/-500 ms;
- elapsed time and real-time factor;
- environment and provenance;
- recording-level paired bootstrap intervals, seed 3800, 2,000 repetitions.

DER is the fraction of scored speaker time lost to miss, false alarm, or
confusion after the configured collar/overlap policy. JER computes a
Jaccard-style error per optimally matched reference speaker and averages across
speakers, so it is sensitive to speakers who are poorly represented even if
they occupy little total time. Neither metric identifies a person by name.

The analysis intentionally does not collapse everything into one composite
rank. Use Pareto comparisons across DER/JER, overlap, count, fragmentation,
latency, and resources.

Typical analysis artifacts include:

```text
overall_results.csv
recording_results.csv
factor_results.csv
speaker_count_results.csv
overlap_results.csv
turn_cadence_results.csv
fragmentation_results.csv
merge_results.csv
single_speaker_controls.csv
reentry_results.csv
resource_results.csv
reliability_summary.csv
oracle_turn_results.csv
paired_comparisons.csv
analysis_manifest.json
report.md
checksums.json
```

### Execution behavior

- Cases run sequentially by design, using the isolated interpreter assigned to
  each pipeline. Parallel execution has not been established as scientifically
  or operationally safe for these shared model/runtime resources.
- A successful checksum-bound case is reused on restart.
- Failed and partial attempts are preserved rather than overwritten silently.
- `STOP_REQUESTED` is checked between cases.
- Evaluation refuses to run without a frozen post-development pipeline config.
- The intended order is validate -> development -> analyze -> freeze ->
  evaluation. Never tune after viewing evaluation results.

### Evidence currently present

- Benchmark preparation and integrity validation passed, including factor
  balance, WAV/reference presence, enrollment/mixture disjointness, source
  hashes, speaker-pool separation, timing, and RTTM checks.
- One reusable, non-scientific `sherpa_onnx_diarization` smoke case exists.
- That single smoke case reported approximately DER 0.6394, JER 0.6949,
  speaker-count MAE 4, and RTF 0.2554. This is an installation signal only.
- Seven other smoke cases were missing because the prior run was limited to one
  case.
- No complete controlled development run exists.
- No `frozen_pipeline_configuration.json` exists.
- No controlled evaluation run exists.
- A read-only development plan for Sherpa, energy+WeSpeaker,
  pyannote+CAM++, and Community-1 counted 60 cases per pipeline / 240 inference
  units; it did not start inference.

## 6. Native-condition Stage 11 evaluation

### Purpose and data

Native Stage 11 evaluates unmodified dataset recordings from frozen Stage 2
source panels. Synthetic augmentation is prohibited.

- **AMI**: array and headset streams with compatible manual timing references.
  Headset scoring has a wearer/reference-scope caveat documented in Stage 11.
- **CHiME-6**: far-field arrays and participant-close streams. Participant-close
  scoring also has a wearer/reference-scope caveat.
- **VOiCES**: current normalized metadata does not provide the fine speech timing
  needed for DER/JER; those metrics are suppressed instead of fabricated.

Manifest identities and counts:

| Tier / ID | Total units | AMI | CHiME-6 | VOiCES | DER/JER eligible | cpWER eligible |
|---|---:|---:|---:|---:|---:|---:|
| small / `native_diarization_c7ee96923354` | 200 | 80 | 80 | 40 | 160 | 44 |
| standard / `native_diarization_cb172bbeb7cb` | 1,118 | 518 | 480 | 120 | 998 | 322 |
| large / `native_diarization_fb4648b2d40f` | 5,808 | 3,168 | 2,400 | 240 | 5,568 | 1,584 |

The policy uses a 0.25-second collar, both overlap-aware and overlap-excluded
views, a UEM, anonymous labels, and estimated speaker count. Reference identity
mapping is prohibited.

### Native result contract

Each successful unit is designed to contain:

```text
run.json
backend_status.json
resolved_component_identity.json
predictions/segments.rttm
references/reference.rttm
references/scored_region.uem
diagnostics/diarization.json
diagnostics/segmentation_provenance.json
diagnostics/alignment_validation.json
metrics/summary.json
predictions/speaker_attributed_transcript.jsonl  # conditional
report/scenario_report.json
report/scenario_report.md
checksums.json
```

Native metrics include DER/JER and their components, speaker-count error,
anonymous-label consistency, and both overlap modes. cpWER is only emitted when
complete reference and hypothesis speaker-attributed transcripts are available.
The current native diarization command does not itself run ASR, so cpWER should
not be expected from a diarization-only result.

### Evidence currently present

Only one Sherpa AMI smoke result is present under
`runs/diarization_evaluation/smoke_sherpa_onnx_diarization_diar_0e112c574a82`.
It is roughly 5.456 seconds long. It reported DER/JER 0 on the scored slice, but
the reference had two labels, the prediction one, and the 0.25-second collar
left only one scored speaker. Treat this strictly as proof that the adapter,
RTTM conversion, and scorer connected; it is not accuracy evidence.

There is no completed native small, standard, or large campaign. The current
native CLI is primarily a one-unit runner; it does not yet offer the same
restart-safe, multi-case campaign controller as the controlled benchmark.

## 7. Hybrid speaker-attribution evaluation

### Purpose and protocol

Protocol identity: `hybrid_speaker_attribution_v1_6c43a2bbe1ca`  
Source benchmark identity: `controlled_diarization_v1_acd5e6e431d8`

The hybrid protocol adds metadata overlays to every controlled case; it does
not copy or change audio:

- `ALL_KNOWN`
- `MIXED_KNOWN_UNKNOWN`
- `ALL_UNKNOWN`

There are 564 overlay units total: 24 smoke, 180 development, and 360
evaluation. The protocol uses 960 unique reserved enrollment clips, with no
enrollment/mixture clip overlap and no development/evaluation speaker overlap.
Every `ALL_UNKNOWN` case includes five background impostor enrollments so the
open-set search is non-empty.

Known references retain exact identities. Unknown references are mapped
optimally to recording-local `Unknown_N` labels for scoring only. Unknown labels
do not persist across recordings, and the scorer never rewrites the underlying
anonymous diarization output.

### Required inputs

A scientific hybrid run needs all of the following:

1. the validated controlled protocol and generated WAVs;
2. a selected controlled diarization pipeline and its complete results;
3. a frozen diarization pipeline config for evaluation;
4. one independently qualified speaker-embedding backend;
5. a scientific `hybrid-enrollment-policy.v1` derived from the enrollment/live
   study, including aggregation and decision-policy provenance;
6. development-only selection of hybrid threshold/margin/evidence settings;
7. a frozen hybrid config before evaluation.

The only enrollment policy currently shipped with this layer is
`hybrid_enrollment_policy_non_scientific_smoke_v1`. It uses CAM++ with a 0.5
threshold and one enrollment utterance. It is deliberately marked
non-scientific and must not be used for the final comparison.

### Embedding cache and attribution modes

The cache key includes audio hash, interval, role, and backend/job identity.
Changing a threshold or attribution policy should replay cached embeddings
without neural inference. Enrollment audio and predicted segments are both
embedded with the selected speaker backend; the hybrid layer does not reuse a
diarizer's private/internal embeddings.

Two decision views exist:

- **final/offline**: uses all eligible evidence for a cluster;
- **progressive**: processes eligible cluster segments in chronological order
  and evaluates evidence checkpoints at 0.5, 0.75, 1, 1.5, 2, 3, and 5 seconds.

Whole segments may overshoot a checkpoint, so realized evidence duration is
recorded. A decision is Known only when the score, Top-1/Top-2 margin, and
minimum-evidence rules pass. Otherwise it is provisional/insufficient or
Unknown/open-set rejected.

This is **causal attribution replay over completed diarization segments**, not a
true end-to-end streaming diarizer. The diarization segmentation/clustering is
already final before progressive identity decisions are replayed.

### Current hybrid metrics

The implemented analysis includes:

- known identity accuracy;
- wrong-known rate;
- known-to-unknown rate;
- unknown rejection rate;
- false-known rate;
- identity coverage;
- identity precision on covered time;
- time-weighted identity accuracy;
- progressive forms of the identity metrics;
- identity churn count;
- mean reported stable-known-identity latency;
- fragmentation, merge, and speaker-count metrics;
- known and unknown re-entry consistency;
- raw/reference/predicted durations;
- preserved anonymous diarization metrics;
- oracle-diarization identity diagnostic;
- runtime/resource result tables;
- recording-level bootstrap intervals, seed 3800, 500 repetitions.

Development analysis adds threshold, evidence-duration, margin, false-known,
and identity-latency curves/tables. See
`docs/automated_evaluation/hybrid_speaker_attribution.md` for exact table names
and columns.

### Required decision gates

```text
select speaker backend + enrollment policy outside hybrid
  -> complete controlled diarization development
  -> freeze exact diarization pipeline/config
  -> run hybrid development only
  -> select and freeze hybrid decision config with rationale
  -> run untouched hybrid evaluation
```

Evaluation validates both frozen hashes and rejects ad hoc threshold, margin,
minimum-evidence, aggregation, or overlap overrides.

### Current evidence

- Hybrid protocol validation passed: 564 overlays, correct source benchmark,
  no development/evaluation speaker intersection, no enrollment/mixture clip
  intersection.
- An audit with CAM++, Sherpa, and the non-scientific smoke policy passed and
  found the reserved enrollment audio.
- The plan reports 60 development cases / 180 overlays, 120 evaluation cases /
  360 overlays, 960 enrollment embeddings, and 3,328 oracle reference-turn
  embeddings.
- Development/evaluation currently have 180 missing controlled diarization
  cases and zero reusable complete cases in that scope.
- The default hybrid result root does not yet exist.
- No scientific enrollment policy, frozen hybrid config, hybrid results, or
  final hybrid report exists.

## 8. Known limitations and implementation issues to resolve before expansion

The following are current-state observations, not completed improvements.

### Protocol/evidence limitations

1. The 27 controlled human-review cases remain unreviewed.
2. The long-session challenge is disabled; the planned design is 12 recordings
   of about 300 seconds.
3. Controlled audio is prompted/read speech in clean synthetic arrangements,
   not spontaneous multi-party device audio.
4. Native data adds realism, but no native campaign has run and VOiCES cannot
   currently yield DER/JER under the available reference metadata.
5. No target-device, room, microphone-distance, household-noise, or spontaneous
   interaction evaluation exists yet.
6. The modular pyannote adapter collapses segmentation channels to speech
   activity before embedding windows. It does not preserve pyannote channels as
   overlapping persistent speaker streams, limiting overlap handling.
7. Current deterministic clustering thresholds are engineering defaults and
   require development-only calibration.
8. No full controlled development/freeze/evaluation chain has been completed.
9. No scientific hybrid enrollment policy or hybrid run exists.

### Hybrid metric semantics that need care

1. Current `unknown_rejection_rate` requires the correctly mapped persistent
   `Unknown_N`, so it mixes *reject as unknown* with *track the right anonymous
   unknown instance*. Add a pure any-Unknown rejection rate and keep instance
   tracking as a separate metric.
2. `stable_known_identity_latency_mean_sec` currently reflects the first correct
   progressive hit; it does not prove that identity remains stable afterward.
   Rename it or implement a sustained-stability definition.
3. Mean identification latency excludes identities that are never identified,
   making the mean optimistic. Report failure probability and censored
   time-to-event statistics.
4. `identity_churn_count` includes expected state acquisition such as
   Provisional -> Known. Split beneficial acquisition from harmful Known <->
   Wrong/Unknown changes and count identity flips separately.
5. Re-entry uses consecutive reference turns without a minimum absence/silence
   threshold. Define re-entry and report absence-duration buckets.
6. Time-weighted correctness credits an interval when the expected label is
   among simultaneous predictions even if extra wrong labels are also present.
   Add exclusive-correct time and over-attribution time.
7. Known-to-Unknown rate applies to covered predicted time; uncovered reference
   speech is represented separately through coverage. Add an end-to-end known
   identity miss rate that includes uncovered time.
8. Progressive scoring obtains the optimal unknown-label permutation from final
   decisions. That is label-invariant, but add explicitly causal unknown-instance
   consistency if the product needs live Unknown tracking.

### Configuration/orchestration mismatches

1. `hybrid_speaker_attribution.v1.yaml` declares
   `multi_template_mean_score` under `development_options.cluster_aggregation`,
   while the current runtime/PowerShell parameter accepts only
   `normalized_mean` or `duration_weighted_mean` for cluster aggregation.
   Multi-template mean is valid for enrollment aggregation. Clarify/fix this
   mismatch before treating the declared grid as executable.
2. `RunDevelopment` runs one supplied runtime configuration at a time; it does
   not automatically expand every value in the YAML development grid. A
   restart-safe grid orchestrator is still needed for exhaustive development.
3. The hybrid PowerShell wrapper has no enrollment-aggregation parameter. It
   inherits that choice from the enrollment-policy file, although lower-level
   freeze/contract logic knows about enrollment aggregation.
4. The native evaluator is one-unit oriented; it lacks a controlled-style
   multi-unit resumable campaign wrapper and dashboard.

### Missing analyses worth prioritizing

- score and Top-1/Top-2 margin distributions by known/unknown condition;
- FPIR, FNIR, and TPIR/DIR at fixed FPIR targets;
- enrollment-set-size scaling;
- identity hubness / which templates attract strangers;
- calibration reliability, ECE, Brier score, and calibration curves;
- time-to-false-known and false-known dwell duration;
- sustained decision stability and harmful identity-flip rate;
- per-speaker and cohort/fairness breakdowns with minimum-support rules;
- room/noise/microphone/distance/overlap condition breakdowns;
- matched peak RAM, CPU/GPU use, energy, model bytes, and template-storage cost;
- paired confidence intervals for JER, error components, speaker count, overlap,
  and re-entry, not DER alone;
- speaker-aware or hierarchical bootstrap. Recording-only bootstrap may
  understate dependence when the same speaker occurs in multiple cases.

ASR/cpWER is not currently part of the hybrid runner. Add it only as a clearly
separate downstream experiment after diarization and identity policy are frozen.

## 9. How to extend the system safely

### Adding a diarization model or pipeline

1. Add or update a component adapter under
   `app/inference_pipeline/diarization/`.
2. Add a component config under `configs/inference/components/diarization/`.
3. Register the exact package environment, model asset paths, acquisition route,
   licences, and expected hashes in the automated-evaluation registries.
4. Add a **new** controlled pipeline ID to
   `controlled_diarization_benchmark.v1.yaml`; do not mutate the meaning of an
   ID already used by results.
5. Ensure status resolves the correct isolated interpreter and all assets with
   network downloads disabled.
6. Add small adapter/RTTM/overlap tests and run one smoke case.
7. Calibrate only on development and record the complete configuration hash.
8. Analyze and freeze the development decision before evaluation.
9. Update the relevant README with purpose, inputs, outputs, Anaconda Prompt and
   PowerShell commands.

### Adding a metric

1. Write its exact numerator, denominator, unit, edge-case behavior, overlap
   semantics, and whether higher/lower is better.
2. Decide whether it belongs to anonymous diarization, identity attribution, or
   downstream ASR. Do not attach identity meaning to anonymous labels.
3. Compute and store a per-recording value before aggregation.
4. Update schemas/contracts, validation, analysis tables, reports, and checksum
   manifests together.
5. Add tiny deterministic tests for perfect, total-failure, empty-denominator,
   overlap, missing-evidence, and multi-speaker cases.
6. Bootstrap at the independent sampling unit appropriate to the claim; consider
   speaker-aware or hierarchical resampling where speakers recur.
7. If a metric affects model/policy selection, add it before development is
   frozen. Do not introduce a new selection rule after evaluation exposure.
8. Version any result-affecting protocol/config change. Preserve old results and
   their hashes.

### Adding a hybrid decision option

Keep these identities separately versioned:

- diarization pipeline and frozen config;
- speaker embedding backend and asset hash;
- enrollment policy and aggregation;
- cluster evidence aggregation;
- score threshold;
- Top-1/Top-2 margin;
- minimum evidence;
- overlap policy;
- progressive checkpoint policy.

Prefer policy replay against cached embeddings for threshold/margin/evidence
experiments. Do not rerun the neural model just because a scalar decision rule
changed.

## 10. Safe inspection and run commands

Open PowerShell or Anaconda Prompt, activate no global environment, and use the
repository-managed interpreters. Start with:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
```

### Read-only/validation checks

```powershell
& ".\scripts\run_controlled_diarization.ps1" -Action Audit
& ".\scripts\run_controlled_diarization.ps1" -Action Validate

$Pipelines = @(
  "sherpa_onnx_diarization",
  "modular_energy_wespeaker",
  "modular_pyannote_campplus",
  "pyannote_community1"
)

& ".\scripts\run_controlled_diarization.ps1" `
  -Action Status `
  -Tier development `
  -Pipelines $Pipelines

& ".\scripts\run_controlled_diarization.ps1" `
  -Action Plan `
  -Tier development `
  -Pipelines $Pipelines
```

Pass the PowerShell array directly with `&` as shown. Starting another
`powershell.exe -File` and passing a comma-separated quoted value can collapse
the pipeline list into one invalid string.

### Intended controlled scientific sequence (does start inference)

Do not run this sequence until pipeline membership and available compute are
approved. The commands are documented here for the receiver, not executed by
this handoff.

```powershell
& ".\scripts\run_controlled_diarization.ps1" `
  -Action Run -Tier development -Pipelines $Pipelines

& ".\scripts\run_controlled_diarization.ps1" `
  -Action Analyze -Tier development -Pipelines $Pipelines

$FrozenDiarization = Join-Path (Get-Location) `
  "JustPeachyResults\diarization\controlled_diarization_v1\frozen_pipeline_configuration.json"

& ".\scripts\run_controlled_diarization.ps1" `
  -Action Freeze `
  -Tier development `
  -Pipelines $Pipelines `
  -FrozenPipelineConfig $FrozenDiarization `
  -DecisionNote "REPLACE WITH THE RECORDED DEVELOPMENT-ONLY DECISION"

& ".\scripts\run_controlled_diarization.ps1" `
  -Action Run `
  -Tier evaluation `
  -Pipelines $Pipelines `
  -FrozenPipelineConfig $FrozenDiarization
```

Monitor without changing results:

```powershell
& ".\scripts\run_controlled_diarization.ps1" `
  -Action Status -Tier development -Pipelines $Pipelines
```

Request a graceful stop between cases:

```powershell
& ".\scripts\run_controlled_diarization.ps1" -Action Stop
```

### Hybrid validation and audit

The following uses the included non-scientific policy only to validate plumbing:

```powershell
$SmokePolicy = ".\configs\automated_evaluation\hybrid_enrollment_policy.non_scientific_smoke.yaml"

& ".\scripts\run_hybrid_speaker_attribution.ps1" -Action Validate -VerifyAudioHashes

& ".\scripts\run_hybrid_speaker_attribution.ps1" `
  -Action Audit `
  -SpeakerBackend "campplus_speaker_embedding" `
  -DiarizationPipeline "sherpa_onnx_diarization" `
  -EnrollmentPolicy $SmokePolicy

& ".\scripts\run_hybrid_speaker_attribution.ps1" `
  -Action Plan `
  -SpeakerBackend "campplus_speaker_embedding" `
  -DiarizationPipeline "sherpa_onnx_diarization" `
  -EnrollmentPolicy $SmokePolicy
```

Do not run scientific hybrid development until a real enrollment-policy file and
the selected controlled diarization development results exist. Do not run hybrid
evaluation until both frozen configs exist and match.

Hybrid status, once a run exists:

```powershell
& ".\scripts\run_hybrid_speaker_attribution.ps1" -Action Status
```

### Native Sherpa smoke shape

Use the ONNX interpreter for native Sherpa, not the core `.venv` interpreter:

```powershell
& "..\..\.stage8-envs\onnx\Scripts\python.exe" `
  ".\run_evaluation.py" diarization smoke `
  --manifest-root ".\benchmarks\stage11\small"
```

Consult `app/diarization_evaluation/README.md` before a different backend or
full native unit. Native campaign orchestration is not yet equivalent to the
controlled wrapper.

## 11. Recommended next work, in order

1. Preserve the current working tree and review uncommitted diarization/hybrid
   diffs before changing contracts.
2. Complete and record the 27-case human audio/reference review.
3. Resolve the hybrid aggregation-grid mismatch and add tests for every declared
   development option.
4. Decide the controlled development pipeline set. If ERes2Net or ReDimNet2 is
   desired, integrate it under a new explicit pipeline ID before development.
5. Run controlled development, analyze failure modes, select/freeze exact
   diarization pipeline configurations, then run evaluation once.
6. Finish the independent speaker enrollment/live study and export a scientific
   enrollment policy for the selected embedding finalist(s).
7. Add a restart-safe hybrid development-grid replay/controller, preferably
   maximizing cached-embedding reuse.
8. Add the open-set and temporal metrics listed above, with precise semantics and
   deterministic tests, before hybrid development selection.
9. Run hybrid development, freeze the decision policy, then run untouched hybrid
   evaluation.
10. Run a finalists-only native-condition campaign to test whether conclusions
    survive AMI/CHiME-6 conditions. Treat VOiCES timing limitations explicitly.
11. Only then add downstream ASR/cpWER, target-device recordings, long sessions,
    and true streaming evaluation.

## 12. Receiver checklist

Before claiming a result is scientific, confirm:

- [ ] exact protocol ID and source hashes are recorded;
- [ ] all model assets resolve locally and implicit downloads are disabled;
- [ ] pipeline/environment/model hashes are in the result;
- [ ] human-review requirement is satisfied or explicitly reported as missing;
- [ ] no development/evaluation speaker or clip leakage exists;
- [ ] development selection happened without evaluation inspection;
- [ ] frozen diarization config matches every evaluation result;
- [ ] frozen enrollment/hybrid policy matches every hybrid evaluation result;
- [ ] missing/failed cases are reported, not silently dropped;
- [ ] metric denominators and empty cases are visible;
- [ ] confidence intervals respect repeated-speaker dependence where applicable;
- [ ] smoke output is labelled non-scientific;
- [ ] no raw audio, archive, gated model asset, credential, or secret is added to Git.

This is the current baseline from which new diarization models, decision rules,
metrics, and user-experience experiments should be designed.
