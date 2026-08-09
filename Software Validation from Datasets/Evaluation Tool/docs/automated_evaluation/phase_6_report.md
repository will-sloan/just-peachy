# Stage 6 Completion Report — Worker Assignment and Result Merge

## Outcome

Stage 6 adds deterministic worker assignments, one-time independent local campaign copies, assignment-scoped execution, checksummed worker transfer packages, independent transfer validation, conflict-safe result merging, and a portable analysis input index. No evaluator, model, augmentation, scorer, plotter, reporter, benchmark hash, or scenario hash behavior changed. No shared SQLite database or network coordinator was added.

## Implemented contracts

- `worker-assignment.v1` and `worker-assignment-hash.v1`;
- `worker-result-transfer.v1` and its complete file/tree inventory;
- `merged-result-index.v1`;
- `merge-validation-report.v1`;
- `analysis-input-index.v1`.

The JSON Schemas are under `configs/automated_evaluation/schemas/`. Assignment manifests are YAML because Stage 3 already reserved `worker_assignments/*.yaml`; all other Stage 6 exchange/index artifacts are JSON. Pickle is not used.

## Partitioning and execution

Assignments support explicit IDs, repeated IDs, inclusive ID ranges, exact component combinations, datasets, panels, stable hash partitions, and a deterministic maximum count. All filters are evaluated against the immutable campaign's resolved scenarios. The modulo partition uses the full global scenario hash. Worker and machine identity do not alter scenario identity.

Each person operates a complete repository clone and a complete local campaign copy. The campaign copy is created only while every scenario is pending. Its SQLite database is copied once and then used only on the worker's local disk. The result handoff excludes all database files.

## Validation and merge

Assignments bind campaign, benchmark, scenario, seed, component, model, Git commit, and environment profile identities. A transfer additionally binds an environment fingerprint, every file's size/hash, each scenario tree hash, and ordinary Stage 3 completion validation. Missing assigned scenarios may be exported later and remain explicit.

Merge validates all sources before copying. Identical duplicate trees are recognized; byte conflicts reject the merge and cannot replace an indexed result. The merge report records package/hardware differences, invalid transfers, incomplete work, duplicates, conflicts, and missing global scenario IDs. The analysis input index lists portable result roots and available prediction, metric, resource, and report artifacts for the later analysis stage.

## Qualification evidence

The Stage 6 suite covers deterministic two-worker partitioning, selectors, overlap, nonexistent scenarios, commit/profile/model/seed mismatches, missing and corrupt files, partial transfers, long paths, identical duplicates, conflicting duplicates, and a complete synthetic two-worker split/run/copy/transfer/merge using independent SQLite files. It requires no GPU, model, credentials, network service, or download.

## Not included

Stage 6 does not implement final comparative analysis, statistical tests, campaign-wide plots/reports, GPU concurrency, a shared coordinator, or network database access. Those remain later work.
