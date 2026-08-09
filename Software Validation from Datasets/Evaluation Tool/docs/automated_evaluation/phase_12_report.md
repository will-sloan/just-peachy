# Stage 12 implementation report

## Delivered boundary

Stage 12 adds campaign-level result reconciliation, a standalone analysis manifest, versioned metric/plot/report registries, typed metric exports, explicit paired comparisons, deterministic cluster-bootstrap intervals, eligibility-gated plots, coverage reconciliation, campaign reports, preregistered shortlist/release rules, and a model-free release-workflow qualification command.

It reuses Stage 3 completion validation, Stage 6 merge validation, existing scenario metric/report artifacts, and Stage 7/9/10/11 scientific outputs. It does not run inference, download models, rescore unsupported outputs, create substitute RIR identities, or alter scenario folders. Each campaign analysis copies the registries, decision policy, and independent analyst guide into `analysis/contracts/`, so interpretation does not require importing execution code.

## Public contracts

- `analysis-manifest.v1` and `campaign-result-index.v1`;
- `campaign-metric-registry.v1`;
- `campaign-plot-report-registry.v1`;
- `campaign-decision-policy.v1`;
- `campaign-coverage-matrix.v1`;
- `paired-campaign-comparison.v1`;
- `campaign-release-qualification.v1`;
- `campaign-plot-metadata.v1`.

Breaking wire or semantic changes require an explicit new version. Rebuilding unchanged inputs preserves the manifest timestamp and produces byte-stable indexes.

## Result admission and missingness

Only a result in the validated Stage 6 merged index that still passes ordinary scenario completion validation is included. Every planned scenario is indexed in campaign order. Failed, missing, invalid, or complete-but-unmerged scenarios remain explicit and block mandatory completion gates. Unsupported metric fields remain null with reasons; every registered plot is either generated with a provenance sidecar or skipped with a reason.

## Statistical policy

Comparisons must be declared explicitly and share benchmark, panel, tier, dataset, scoring policy, and stable item IDs. Stage 12 reports unmatched and invalid counts, paired absolute/relative changes, paired standardized effect size, and a seed-3800 cluster bootstrap. Benjamini–Hochberg adjustment is implemented for preregistered confirmatory families. No automatic baseline guessing or full Cartesian model comparison was added.

## Release workflow

The synthetic gate runs existing Stage 4/6 model-free qualifications for transient retry/partial preservation, timeout, interruption/resume, stop requests, stale-lease restart recovery, independent two-worker execution, checksummed transfers, environment-difference reporting, merge reconciliation, and long Windows-safe paths. Progression remains synthetic → small → standard → large. GPU concurrency remains one until separately qualified.

The persistent qualification at `runs/stage12_release_qualification/` passed all nine collected test cases (eight selected nodes, including the two checksum-corruption parameter cases) in 63.32 seconds. The JSON records every required evidence flag and the log preserves the exact pytest outcome. Temporary campaign/test directories are discarded after qualification; only the compact evidence and log remain.

## Verification

- Stage 12 suite: 9 passed, covering registry completeness, a full two-worker merged analysis, byte stability, partial-merge gaps, paired statistics, duplicate-key rejection, multiple-comparison adjustment, manifest corruption, CLI, and schemas.
- Final affected-path checks after the declarative table registry, repeated-finalist variance, duration accounting, and standalone guide copy: 5 passed.
- Prior-stage regressions: 142 passed and one expected unavailable-CUDA telemetry test skipped across Stages 3–11; optional heavyweight real-model reruns were excluded because Stage 12 must not rerun inference.
- Ruff: all Stage 12 source, CLI integration, and tests passed.
- Public schema audit: all five Stage 12 JSON Schema documents parsed successfully.

## Stage boundary

No small, standard, or large inference campaign is executed by Stage 12 implementation itself. Those gates require completed campaign evidence. Missing model credentials/assets and invalid scientific prerequisites remain explicit `unavailable`, `deferred`, or `unexpected_missing` coverage rather than being acquired or fabricated.
