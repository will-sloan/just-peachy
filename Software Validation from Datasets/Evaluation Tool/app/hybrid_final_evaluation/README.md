# Frozen final hybrid speaker-attribution evaluation

## Purpose

This package runs Task 2 of the Hybrid Product V2 study. It consumes the exact
Task-1-frozen H2/H5/H4 decision, reuses the completed held-out anonymous
diarization RTTMs, independently extracts evaluation-tier identity embeddings,
and replays only the frozen open-set and user-visible label policy. It never
recalibrates on evaluation and does not run ASR, cpWER, XVF3800 audio, or model
fine-tuning.

CHiME-6 is recorded as `CHIME6_HYBRID_NOT_SCIENTIFICALLY_SUPPORTED` because
Task 1 could not prove close/far source-time and synchronized-duplicate
disjointness. VOiCES is recorded as `NOT_SUPPORTED` because Task 1 did not
freeze a speaker-identity enrollment/probe mapping. The tool does not fabricate
metrics for either scope.

## Inputs

- `JustPeachyResults/hybrid_speaker_attribution_product_v2_development/frozen_hybrid_product_v2_selection.yaml`
  and its SHA-256 sidecar.
- The Task-1 development identity tables and exact result-affecting source
  hashes referenced by that freeze.
- `JustPeachyResults/diarization_finalists_final_evaluation/controlled_v1` and
  `controlled_v2`, containing all frozen evaluation-tier anonymous RTTMs.
- Evaluation cases under `benchmarks/stage11/controlled_diarization_v1` and
  `benchmarks/stage11/diarization_product_v2`.
- Evaluation-only identity overlays under
  `benchmarks/hybrid_speaker_attribution/hybrid_speaker_attribution_product_v2`.
- Reserved Common Voice evaluation enrollment clips resolved through
  `JP_DATA_ROOT` and unchanged controlled WAVs under `JustPeachyGeneratedData`.

## Outputs

Results are written under
`JustPeachyResults/hybrid_speaker_attribution_product_v2_final_evaluation`.
Important outputs are `analysis/REPORT.md`, `analysis/METRIC_GUIDE.md`,
`analysis/finalist_summary.csv`, `analysis/overlay_results.csv`,
`analysis/label_event_log.csv`, `analysis/analysis_manifest.json`, and
`final_hybrid_product_v2_selection.yaml`.

The compact upload ZIP is written under `JustPeachyResearchSummaries`. It
contains reports, tables, plots, policies, frozen decisions, event logs,
validation, provenance, checksums, and inventories. Raw audio, model weights,
credentials, embedding caches, and large score bundles are excluded.

## PowerShell / command line

From the repository root:

```powershell
$Runner = "Software Validation from Datasets\Evaluation Tool\scripts\run_hybrid_speaker_attribution_final_evaluation.ps1"

powershell -ExecutionPolicy Bypass -File $Runner -Action Validate
powershell -ExecutionPolicy Bypass -File $Runner -Action Plan
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -ParallelBackends 2 -BootstrapRepetitions 500 -OpenMonitor
powershell -ExecutionPolicy Bypass -File $Runner -Action Status
powershell -ExecutionPolicy Bypass -File $Runner -Action Stop
```

The full run is restart-safe. Repeat the same `-Action Run` command after an
interruption; valid per-segment caches and checksum-bound score bundles are
reused. `Stop` finishes active backend workers or the current score unit before
stopping. Closing the monitor does not stop science.

Scope-specific commands:

```powershell
powershell -ExecutionPolicy Bypass -File $Runner -Action RunControlled -ParallelBackends 2
powershell -ExecutionPolicy Bypass -File $Runner -Action RunCHIME6
powershell -ExecutionPolicy Bypass -File $Runner -Action RunVOICES
powershell -ExecutionPolicy Bypass -File $Runner -Action Analyze -BootstrapRepetitions 500
powershell -ExecutionPolicy Bypass -File $Runner -Action Collect
```

## Anaconda Prompt

No new Conda environment is needed. The controller launches each frozen
backend in its already-qualified local environment. In Anaconda Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
".venv\Scripts\python.exe" "Software Validation from Datasets\Evaluation Tool\run_evaluation.py" hybrid-final-evaluation validate
".venv\Scripts\python.exe" "Software Validation from Datasets\Evaluation Tool\run_evaluation.py" hybrid-final-evaluation plan
".venv\Scripts\python.exe" "Software Validation from Datasets\Evaluation Tool\run_evaluation.py" hybrid-final-evaluation full --parallel-backends 2 --bootstrap-repetitions 500
```

The controller accepts no threshold, margin, enrollment, label-policy, overlap,
or expiry override. Those values come only from the checksum-bound Task-1
freeze.

