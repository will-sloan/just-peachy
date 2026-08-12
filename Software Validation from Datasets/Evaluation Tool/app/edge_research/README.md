# Edge research planner

This additive package resolves already-registered components into deterministic,
environment-isolated scenario catalogs. It does not run inference or download models.

From an Anaconda Prompt or PowerShell opened at the repository root:

```powershell
..\..\.venv\Scripts\python.exe -m app.edge_research.cli plan
..\..\.venv\Scripts\python.exe -m app.edge_research.cli verify
```

Run those commands from `Software Validation from Datasets\Evaluation Tool`, or use
the repository-level PowerShell wrappers documented in
`docs/automated_evaluation/edge_research_quick_start.md`.

Inputs are the frozen `benchmarks/v1` manifests, component/model registries, existing
inference YAML fragments, approved condition sets, and Stage 10 manifests. Outputs are
written under `benchmarks/edge_research`: the plan, queue, per-environment JSONL scenario
catalogs, hashes, and Stage 10 execution-plan metadata. Source audio is never copied.
