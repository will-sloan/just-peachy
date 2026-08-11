# Stage 14 launch helpers

## Purpose

These scripts are thin launch-day wrappers around the existing Evaluation Tool
CLI. They materialize the frozen campaign candidate, inspect every assigned
scenario, run exactly one worker assignment, export checksummed results, merge
independent transfers, and invoke the existing analysis workflow. They do not
implement a second executor, store secrets, download models, or enable parallel
GPU jobs.

## Inputs and outputs

Inputs are either the preserved CPU `launch_package.v1.yaml` or the CUDA
successor `launch_package.gpu.v1.yaml`, a complete repository clone at its
expected/bound commit, local datasets, the exact Whisper Base asset, and one
generated worker assignment. Runtime outputs are written under the selected
campaign in `automated_runs`; machine-local preflight JSON is written to
`artifacts/launch_readiness`; transfer packages default to the repository-level
`transfer_packages` folder.

## PowerShell

Run from `Software Validation from Datasets/Evaluation Tool`:

```powershell
python scripts/materialize_launch_campaign.py --bind-current-commit
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1 -PreflightOnly
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1
```

The CPU wrappers bind `campaign_05_massive_release`, `core-cpu`, `cpu`, and
`float32`. The GPU wrappers bind `campaign_06_massive_release_cuda`,
`core-cuda`, `cuda:0`, and `float32`. Every launch wrapper supports
`-PreflightOnly`, which runs the complete production preflight and exits before
the executor starts.

After a deliberate stop, resume only the current worker's assignment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1 -ResumeStopped
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1 -ResumeStopped
```

After every assigned scenario succeeds:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export_machine_a_results.ps1
powershell -ExecutionPolicy Bypass -File scripts/export_machine_b_results.ps1
powershell -ExecutionPolicy Bypass -File scripts/merge_massive_campaign.ps1
powershell -ExecutionPolicy Bypass -File scripts/analyze_massive_campaign.ps1 `
  -PrerequisiteEvidence automated_runs/campaign_04_standard_release/analysis/report/release_qualification.json
```

Each launch wrapper first validates the global campaign, both assignments, the
local machine profile, and every scenario in its assignment. A preflight
blocker returns non-zero before inference starts. Export refuses to overwrite a
destination and refuses to call a partial transfer complete.

`--bind-current-commit` is the clean post-commit release path. It avoids an
impossible self-referential commit hash in a tracked file by deterministically
binding both ignored runtime assignments to the checkout's actual HEAD. Both
machines must compare
`automated_runs/campaign_05_massive_release/worker_assignments/release_binding.json`;
the files must be byte-identical before launch. Omit the flag only to reproduce
the pre-commit candidate identities recorded in the versioned package.

## Anaconda Prompt or Command Prompt

Anaconda is optional. Ordinary Command Prompt works with the repository virtual
environment:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python scripts\materialize_launch_campaign.py --bind-current-commit
powershell -ExecutionPolicy Bypass -File scripts\launch_campaign_machine_a.ps1
```

The command without the flag is retained only to reproduce the candidate
identities recorded in the selected launch package.

Use the Machine B wrapper on the second clone. Do not run both wrappers against
one shared campaign database on a network drive.

## Verification

```bat
python -m pytest tests\automated_evaluation\test_stage14_launch_readiness.py tests\automated_evaluation\test_stage6_campaign_exchange.py -q --basetemp artifacts\pytest_stage14
python -m ruff check --no-cache app\launch_readiness scripts\launch_readiness_probe.py scripts\materialize_launch_campaign.py tests\automated_evaluation\test_stage14_launch_readiness.py
```

The launch-day source of truth is
`docs/automated_evaluation/launch_control_sheet.md`.

## Word operator documents

`generate_operator_word_docs.py` converts the eleven canonical launch/asset Markdown
files into the numbered `.docx` files under
`docs/automated_evaluation/Word Documents`. It changes documentation only; it
does not materialize or execute a campaign. Its inputs are the Markdown files
listed in the script's `DOCUMENTS` mapping. Its outputs are the eleven same-named
operator Word documents.

The repository runtime environments do not require `python-docx`. On this
workstation, run the documentation utility from Anaconda Prompt or PowerShell
with the Anaconda interpreter that already contains `python-docx`:

```powershell
cd C:\Users\amiri\Documents\GitHub\just-peachy
C:\Users\amiri\anaconda3\python.exe "Software Validation from Datasets\Evaluation Tool\scripts\generate_operator_word_docs.py"
```

After generation, render every document with the approved document-rendering
tool and inspect every page before publishing it. The Markdown source remains
canonical; edit Markdown and regenerate rather than hand-editing a `.docx`.

## CUDA successor campaign

The CPU launch package remains immutable. Generate the CUDA scenario catalog and
its coverage-preserving successor package with the repository CPU environment;
these commands do not run inference:

```powershell
python scripts/build_benchmark_contracts.py --reuse-manifests-from benchmarks/v1 --output benchmarks/v1 --pipeline-config configs/inference/whisper_base_cuda_float32.yaml --scenario-catalog-name resolved_scenarios_cuda_float32.jsonl --scenario-summary-name scenario_catalog_cuda_float32_summary.json
python scripts/build_gpu_launch_package.py
python scripts/materialize_launch_campaign.py --launch-package configs/automated_evaluation/launch_package.gpu.v1.yaml --bind-current-commit
```

Inputs are the frozen CPU launch package, the unchanged versioned Parquet
manifests, and the explicit `cuda:0`/`float32` Whisper Base configuration. Outputs
are the CUDA scenario catalog, the GPU launch package, and an ignored materialized
campaign under `automated_runs/campaign_06_massive_release_cuda`. The GPU package
records the preserved CPU identity and maps every selected CPU coverage cell to a
new scenario ID; it never rewrites CPU scenarios as CUDA scenarios.

From Anaconda Prompt or Command Prompt, activate the isolated environment before
GPU preflight or inference:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.stage8-envs\core-cuda\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python ..\..\scripts\verify_install.py --profile dev --device cuda --cache-root ..\..\models\cache --whisper base --require-models
```

For a bounded five-item CPU float32 versus CUDA float32/float16 qualification
through the ordinary evaluator, activate `core-cuda` and run:

```powershell
python scripts/run_cuda_qualification.py --max-recordings 5
```

Inputs are the first deterministic CMU Arctic selection, the same local Whisper
Base checkpoint, no augmentation, and beam size 1. Each case produces the normal
predictions, metrics, plots, diagnostics, and report. The wrapper adds 0.25-second
process-tree/NVML samples and writes
`artifacts/gpu_qualification/comparison/whisper_base_cuda_qualification.json`.
This evidence is machine-local and must not be committed as a campaign result.

After materialization, Machine A uses
`scripts/launch_campaign_machine_a_gpu.ps1`; Machine B uses the corresponding
`machine_b_gpu` wrapper only after its own CUDA preflight passes. GPU-specific
export, merge, and analysis wrappers are `export_machine_a_gpu_results.ps1`,
`export_machine_b_gpu_results.ps1`, `merge_gpu_campaign.ps1`, and
`analyze_gpu_campaign.ps1`. Their inputs and outputs are identical to the CPU
wrappers except that they bind `campaign_06_massive_release_cuda`, `core-cuda`,
`cuda:0`, and the measured operational choice `float32`. Float16 remains a
qualified comparison mode, but the bounded Machine A benchmark did not show a
speed advantage and therefore it is not the launch default.
