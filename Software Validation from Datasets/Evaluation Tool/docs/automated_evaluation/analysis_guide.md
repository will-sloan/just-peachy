# Independent analyst guide for automated evaluation campaigns

## Scope and safety boundary

This guide explains how an analyst who did not run the models can validate, load, compare, plot, and report a completed campaign. Stage 12 reads existing campaign artifacts. It does **not** rerun inference, augmentation, scoring, enrollment, diarization, or model loading. If analysis reports a missing or incompatible artifact, resolve the campaign handoff or eligibility issue; do not fill the gap by copying a reference value into a prediction or inventing a metric.

Scientific analysis admits a scenario only when both conditions hold:

1. Stage 6 included the globally identified scenario in its validated merged-result index.
2. The existing Stage 3 completion validator still classifies the copied scenario folder as `complete`.

All planned scenarios remain in `analysis_manifest.json`. Failed, missing, invalid, and complete-but-unmerged work is visible in denominators, coverage, and the final report.

## Prerequisites

- A complete clone of the repository at the expected Git commit.
- The pinned core environment from the repository bootstrap instructions.
- A campaign folder containing `campaign_manifest.json`, the copied benchmark manifests, resolved scenarios, and Stage 6 analysis indexes.
- Copied worker results that passed checksum, schema, global identity, model/config identity, seed, and environment validation.
- Enough disk space for plots and table exports. Stage 12 does not copy source audio or model assets.
- No API key is required for analysis. Never place credentials, private identity mappings, source audio, or absolute private paths in shared analysis artifacts.

Before analysis, verify that Stage 6 reports no conflicting duplicates or incomplete transfers. Environment differences can be warnings, but they must remain visible and may invalidate performance comparisons.

## Anaconda Prompt and Command Prompt workflow

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py campaign validate --campaign-root automated_runs\<campaign_id>
python run_evaluation.py campaign validate-merged --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis index --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis validate --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis run --campaign-root automated_runs\<campaign_id> --prerequisite-evidence C:\results\previous_gate.json
python run_evaluation.py analysis coverage --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis release-status --campaign-root automated_runs\<campaign_id> --prerequisite-evidence C:\results\previous_gate.json
```

`previous_gate.json` is the `release_qualification.json` from the required preceding gate: synthetic before small, small before standard, and standard before large. Omit it to inspect an intentionally blocked first pass.

## PowerShell workflow

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'

python run_evaluation.py campaign validate-merged `
  --campaign-root automated_runs/<campaign_id>
python run_evaluation.py analysis run `
  --campaign-root automated_runs/<campaign_id> `
  --prerequisite-evidence C:/results/previous_gate.json
```

## What to load first

Start with these five files; none requires importing execution code:

1. `analysis/analysis_manifest.json` — campaign identities, benchmark hashes, contracts, scenario index, assignments, merge provenance, and explicit gaps.
2. `analysis/campaign_result_index.json` — exact planned/included reconciliation and artifact paths.
3. `analysis/tables/scenario_metric_values.parquet` — typed registered scenario-level values and explicit availability reasons.
4. `analysis/coverage_matrix.json` — planned-versus-observed status for every component, environment, panel, scenario family, metric, artifact, plot, report, and Stage 12 CLI command.
5. `analysis/report/campaign_report.json` — machine-readable final summary and limitations.

Verify `analysis/analysis_checksums.json` after copying the analysis folder. Plot sidecars identify the exact analysis manifest, scenario IDs, benchmark manifests, aggregation, filters, statistics, limitations, and interpretation section.

## Reproducible analysis workflow

1. Validate the campaign and merged results.
2. Build or refresh the standalone analysis manifest. Rebuilding unchanged inputs is byte-stable.
3. Inspect `failed_missing_invalid_excluded` before looking at quality metrics.
4. Confirm environment fingerprints and any merge warnings.
5. Declare compatible paired comparisons. Do not let the tool guess which scenario is a scientific baseline.
6. Run Stage 12. Existing scenario metrics and reports are reused; unsupported families are skipped.
7. Inspect `metric_availability.json` and `plot_status.json`.
8. Review coverage blockers and release-gate checks.
9. Read the JSON report before its Markdown rendering.
10. Preserve the analysis manifest, copied registries, policy, checksums, and report together.

## Declaring paired comparisons

Use the same frozen benchmark items and scoring policy. The baseline and candidate must match on benchmark manifest identity, panel, tier, dataset slice, and scoring-policy version. The item tables must have a shared unique stable key.

```bat
python run_evaluation.py analysis run ^
  --campaign-root automated_runs\<campaign_id> ^
  --comparison scenario_<baseline>,scenario_<candidate>,micro_wer,wer ^
  --comparison scenario_<baseline>,scenario_<candidate>,latency_p95_sec,latency_sec
```

For direct analysis of two already selected item tables:

```bat
python run_evaluation.py analysis compare ^
  --baseline-item-metrics C:\results\baseline.parquet ^
  --candidate-item-metrics C:\results\candidate.parquet ^
  --baseline-scenario-id scenario_<baseline> ^
  --candidate-scenario-id scenario_<candidate> ^
  --metric wer
```

The comparison reports baseline, candidate, shared, valid, unmatched, and invalid counts; absolute and relative mean change; paired standardized effect size; and a deterministic cluster-bootstrap confidence interval.

## Metric registry

`analysis/contracts/metric_registry.v1.yaml` is the authoritative registry copied into each analysis handoff. Every metric defines its name/version, purpose, eligible scenario types, required fields, source paths, formula, numerator, denominator, aggregation, missing/failure policy, grouping, statistics, limitations, plots, tables, and this interpretation guide anchor.

### Completeness and reliability

`scenario_completion` is 1 only for a validated merged result and 0 for every other planned scenario. `failure_rate` uses declared selected-item or planned-scenario denominators; it never drops failed records silently. Always interpret quality and speed beside completion, empty/missing output, timeout, OOM, and failure counts.

### ASR metrics

`micro_wer` weights by reference word count: `(S + I + D) / reference words`. `micro_cer` uses character errors divided by reference characters. Macro and grouped values remain in existing scenario reports when supported; Stage 12 does not relabel a macro value as micro. WER/CER comparisons require the same normalization and scoring-policy version. Empty hypotheses may be valid scored outputs; missing predictions are failures, not empty text.

### VAD and segmentation

Speech precision/recall, false-alarm duration, missed speech, boundary deviation, region IoU, fragmentation, and merge rates require compatible timing references and a declared collar/tolerance. Stage 12 registers speech recall and false-alarm duration summaries but emits neither when the required reference fields are absent. Downstream WER changes are separate from intrinsic VAD quality.

### Performance and resources

Real-time factor is wall inference seconds divided by processed audio seconds; throughput is its reciprocal only when both use the same measured boundary. Tail latency must state its population. CPU, RAM, VRAM, disk, power, and temperature are sampled measurements; unsupported sensors remain null with availability reasons. Compare machines only when workload, environment, warm/cold state, and measurement policy are compatible. Initialization and warm inference are not interchangeable.

### Speaker protocol metrics

EER, FAR/FRR, TAR at FAR, ROC/DET, top-k identification, and unknown rejection are valid only with backend-specific enrollment, disjoint calibration/evaluation probes, held-out unknown speakers, and compatible model/config/dimension/preprocessing identities. `Unknown` is a scored output. Never replace it with a reference identity, null, empty string, or first enrolled speaker. Keep open-set and closed-set results separate.

### Diarization metrics

DER requires valid aligned RTTM, UEM/scored regions, reference version, collar, overlap policy, and scoring-policy version. JER requires compatible speaker sets and permutation-aware scoring. Do not emit DER/JER when references or timebases are incompatible. Anonymous diarization labels are not known identities. Oracle and estimated speaker-count experiments must remain separately labelled.

### Synthetic release rehearsal

`synthetic_success` proves campaign mechanics only. It makes no claim about speech accuracy, latency, model reliability, CUDA, or scientific conclusions.

## Statistical methods and assumptions

Use paired comparisons whenever scenarios share items. Stage 12 clusters in this priority: speaker, meeting, session, source recording, recording, item. The deterministic bootstrap resamples clusters with seed 3800 and reports the mean paired difference interval. This respects repeated observations better than treating every utterance as independent, but it still assumes sampled clusters represent the target population.

Always report:

- valid pair and unmatched counts;
- total evaluated duration when present;
- absolute and relative changes;
- confidence interval and method;
- effect size;
- repeated-finalist variance;
- failed, missing, malformed, duplicate, and unexpected outputs.

If three or more confirmatory comparisons are interpreted together, apply the preregistered Benjamini–Hochberg correction and retain the unadjusted values. Exploratory plots must be labelled exploratory. A confidence interval is not a practical-significance threshold. Predeclare shortlist and release rules before final release data is opened.

## Interpreting plots

Every generated PNG has a `.metadata.json` sidecar. A plot is absent only when `plot_status.json` records why its registered requirements were not met.

### Pareto frontiers

Lower WER and lower RTF are preferred in the default view. A point is not “best” merely because it lies on the frontier; accuracy, resources, reliability, robustness, and deployment constraints remain separate objectives. Never eliminate a candidate solely for being slower.

### ASR plots

WER/CER bars describe registered scenario summaries. Check counts, benchmark identity, conditions, and missing output before comparing heights.

### Robustness plots

Clean-to-degraded changes should be paired on the same source utterances. Report clean value, degraded value, absolute change, relative change, and failed/missing differences.

### Exact-RIR plots

The heatmap keeps each exact RIR identity. Dining room, bedroom, and restaurant are separate environments; no ParkingLot or other RIR can stand in for a missing room. Interpret only actual resolved identifiers and hashes. Native noisy/reverberant panels must not appear in synthetic RIR comparisons.

### Native-condition plots

AMI, VOiCES, CHiME-6, and approved `other` rows remain native-only. Group by compatible meeting/session, stream, microphone/device, distance/location, and scored region. Do not infer a controlled causal effect from native-condition differences.

### Speaker-protocol plots

Score distributions, ROC/DET, thresholds, and embedding drift must use the declared backend and held-out split. Threshold curves from calibration describe threshold selection; reported evaluation performance comes from held-out evaluation probes.

### Diarization plots

Confirm collar, overlap policy, UEM, reference version, timebase validation, and segmentation provenance. Missing bars can indicate invalid references rather than good performance.

### Machine comparisons

Environment differences are not automatically errors, but package, Git, model, hardware, CUDA, and sensor differences can confound timing/resource results. Accuracy outputs should remain unchanged across compatible deterministic runs.

### Subgroup analysis

Use only authorized demographic fields. Report counts and uncertainty, avoid ranking tiny groups, and treat findings as diagnostic unless the design supports confirmatory inference. Privacy-safe IDs must stay separate from private real-name maps.

### Qualitative error analysis

Failure-category plots count explicit records. Inspect representative diagnostics without exposing private content. Do not remove failures from denominators because they are difficult to categorize.

## Decision profiles and release gates

`analysis/contracts/analysis_decision_policy.v1.yaml` is frozen before release analysis. The default shortlist preserves a Pareto set over WER, RTF, optional peak VRAM, and failure rate, with minimum valid-output and reliability gates. Whisper Base remains the reference ASR for component screening. WER-only elimination is prohibited.

Release progression is sequential:

1. **Synthetic** — two-worker-equivalent split/run/transfer/merge, checksums, timeout/retry, interruption/resume, stop request, stale-lease restart recovery, long paths, and exact reconciliation.
2. **Small** — all small campaign scenarios validate, no unexplained mandatory coverage gaps, and synthetic evidence passes.
3. **Standard** — the standard campaign passes the same common gates and carries passed small evidence.
4. **Large** — release-level validation only, after the standard gate passes.

GPU concurrency remains one scenario at a time until a separate sustained single-versus-dual qualification demonstrates safe VRAM headroom, meaningful throughput improvement, acceptable latency degradation, unchanged outputs/accuracy, no CPU/RAM/disk bottleneck, and long-run reliability.

## Synthetic two-machine qualification

Run from the Evaluation Tool folder:

```bat
python run_evaluation.py analysis qualify-synthetic ^
  --project-root . ^
  --output-root runs\stage12_release_qualification
```

The command reuses existing model-free Stage 4 and Stage 6 synthetic tests. It covers transient retry and partial preservation, timeout, interruption/resume, stop requests, stale-running recovery, two independent worker databases, transfer and checksum validation, environment-difference reporting, conflict-safe merge, long paths, and global reconciliation. Its JSON and log are evidence for the synthetic gate.

## Coverage reconciliation

Coverage rows use only these statuses:

- `implemented_qualified` — implemented and supported by qualifying observed evidence;
- `unavailable` — prerequisite output, sensor, model, credential, or compatible reference was unavailable;
- `partial` — some but not all planned/supportable coverage exists;
- `deferred` — intentionally left to a later authorized phase or report pass;
- `excluded` — not applicable under the declared campaign scope;
- `unexpected_missing` — mandatory planned coverage has no explained valid result.

Any mandatory unexplained gap blocks release. Optional unsupported metrics and plots do not block by themselves, but their reasons remain in the report.

## Troubleshooting

### “Merged result index is missing”

Run worker export/transfer validation and `campaign merge-results` first. Do not point Stage 12 directly at arbitrary scenario folders.

### “Included scenario no longer validates”

Re-run `campaign validate-artifacts`. A file may be truncated, modified, incompletely transferred, or inconsistent with its checksum/count/schema. Restore from the verified transfer; never edit the merged copy in place.

### “Comparison has incompatible benchmark/scoring field”

Choose scenarios that share the exact manifest, panel, tier, dataset slice, and scoring policy. Cross-dataset or cross-policy summaries can be shown descriptively but are not item-paired tests.

### “No shared stable item key” or duplicate key

Inspect the existing item-metric schema. Fix the producing scenario in a future version; do not generate row numbers as identities.

### Plot skipped

Read `plot_status.json`. Missing RTTM, UEM, threshold sweeps, similarity scores, grouped metrics, resource sensors, exact RIR identities, or compatible native scenarios are legitimate skip reasons.

### Release blocked despite successful model outputs

Check missing/excluded scenarios, mandatory coverage, prerequisite gate evidence, and the Stage 6 merge. A quality score cannot override an incomplete campaign contract.

### Analysis changed after copying

Compare `analysis_checksums.json`, campaign/manifest hashes, copied registries, Git commit, and environment fingerprints. Reject incomplete or modified transfers.

## Reproducibility checklist

- campaign ID and campaign-manifest SHA-256;
- analysis-manifest ID/SHA-256;
- benchmark manifest IDs/SHA-256 values;
- scenario schema/hash/canonicalization versions and global IDs;
- component config/model identities and hashes;
- seed, repetition, device, dtype, runtime, timeout, resource, scoring, and failure policy;
- exact noise/SNR and exact RIR identifier/hash;
- worker assignments and merge report;
- Git, package, OS, CPU, RAM, GPU UUID, driver, CUDA, timezone, and clock metadata;
- scenario and analysis checksums;
- metric/plot registry and decision-policy hashes;
- explicit exclusions, failed/missing outputs, and plot skips;
- statistical pair key, cluster key, seed, repetitions, correction policy, and limitations.

## Final campaign report template

1. Campaign objective and predeclared hypotheses.
2. Manifest, scenario, Git, environment, model, component, and scoring identities.
3. Planned versus realized coverage and all exclusions.
4. Dataset/panel/condition counts and durations.
5. Reliability and failure analysis before quality metrics.
6. ASR, VAD/segmentation, speaker, diarization, performance, and resource results only where supported.
7. Paired estimates, confidence intervals, effect sizes, cluster policy, repeated variance, and multiple-comparison treatment.
8. Pareto/shortlist decision under the frozen policy.
9. Machine/environment differences and reproducibility checks.
10. Release-gate result, blockers, limitations, and exact next action.

The generated `report/campaign_report.json` is the authoritative machine-readable summary; Markdown is a human-readable rendering of the same analysis inputs.
