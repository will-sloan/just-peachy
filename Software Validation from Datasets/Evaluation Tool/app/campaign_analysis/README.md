# Campaign analysis (Stage 12)

## Purpose

This package turns a validated Stage 6 campaign handoff into a standalone result index, registered metric table, paired comparisons, eligibility-gated plots, coverage reconciliation, campaign report, and preregistered release-gate decision. It consumes existing scenario metrics and reports. It does not run inference, rescore an item when a valid scenario metric already exists, download a model, or mutate scenario results.

Only scenarios present in the validated Stage 6 merged-result index and accepted by the existing Stage 3 completion validator are included in scientific analysis. Planned failed, missing, invalid, complete-but-unmerged, and explicitly excluded scenarios remain in every denominator and report.

Re-running `analysis index` is idempotent. On Windows, an existing byte-identical
analysis contract is retained instead of being replaced, avoiding a needless
sharing-lock failure while preserving checksum and incompatibility checks.

## Inputs

- `automated_runs/<campaign_id>/campaign_manifest.json` and detached checksum;
- immutable benchmark manifests and resolved scenarios already copied into the campaign;
- the Stage 6 `analysis/merged_results/merged_result_index.json`, `analysis_input_index.json`, and merge-validation report;
- complete scenario folders with existing predictions, metrics, resource logs, and reports;
- `configs/automated_evaluation/metric_registry.v1.yaml`;
- `configs/automated_evaluation/plot_report_registry.v1.yaml`;
- `configs/automated_evaluation/analysis_decision_policy.v1.yaml`;
- optional previously passed release-gate evidence and explicit paired-comparison declarations.

## Outputs

Stage 12 writes under the existing campaign `analysis/` folder:

```text
analysis/
  analysis_manifest.json
  campaign_result_index.json
  analysis_summary.json
  analysis_checksums.json
  contracts/                 # copied registries, decision policy, and analyst guide
  metric_availability.json
  comparisons.json
  coverage_matrix.json
  plot_status.json
  tables/
    scenario_index.csv
    scenario_metric_values.parquet
    scenario_metric_values.csv
    comparisons.csv
    coverage_matrix.csv
    failure_categories.csv
    repeated_finalist_variance.csv
  plots/
    <eligible plot>.png
    <eligible plot>.png.metadata.json
  report/
    campaign_report.json
    campaign_report.md
    coverage_report.md
    release_qualification.json
```

The copied `analysis/contracts/` files make the handoff interpretable without importing execution code. Every generated plot has a provenance sidecar. Every ineligible plot has an explicit row in `plot_status.json`.

## Run from Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py campaign validate-merged --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis index --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis validate --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis run --campaign-root automated_runs\<campaign_id> --prerequisite-evidence C:\results\previous_gate.json
python run_evaluation.py analysis coverage --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis release-status --campaign-root automated_runs\<campaign_id> --prerequisite-evidence C:\results\previous_gate.json
```

Declare a compatible paired comparison without editing configuration:

```bat
python run_evaluation.py analysis run ^
  --campaign-root automated_runs\<campaign_id> ^
  --comparison scenario_<baseline>,scenario_<candidate>,micro_wer,wer
```

Qualify campaign mechanics without a model or GPU:

```bat
python run_evaluation.py analysis qualify-synthetic ^
  --project-root . ^
  --output-root runs\stage12_release_qualification
```

## Run from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python run_evaluation.py analysis run `
  --campaign-root automated_runs/<campaign_id> `
  --prerequisite-evidence C:/results/previous_gate.json
```

## Tests

```bat
python -m pytest tests\automated_evaluation\test_stage12_campaign_analysis.py -q --basetemp artifacts\pytest_stage12
python -m ruff check app\campaign_analysis tests\automated_evaluation\test_stage12_campaign_analysis.py
```

The complete independent-analyst workflow, statistical assumptions, interpretations, release gates, and troubleshooting guidance are in `docs/automated_evaluation/analysis_guide.md`.
