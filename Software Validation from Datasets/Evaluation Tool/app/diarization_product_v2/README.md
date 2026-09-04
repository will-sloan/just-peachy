# Product-Focused Standalone Diarization Development Study

## Purpose and firewall

This package builds and operates the additive `diarization_product_v2` anonymous diarization study. It compares complete diarizers and modular segmentation/embedding/clustering systems on frozen controlled V1 development plus a product-focused V2 development panel. It measures whether anonymous tracks are accurate, clean, stable, timely, and computationally practical for a later Beaker identity layer.

This code never assigns real names, reads an enrollment database, runs hybrid attribution, applies identity thresholds, runs ASR, or fine-tunes a model. Task 1 analyzes **development only** and freezes `frozen_diarization_development_selection.yaml`. Controlled evaluation and the final CHiME-6 finalist comparison remain locked for Task 2.

Product V2 mixtures are explicitly `evaluation_only=true` and `training_eligible=false`. They use real Common Voice 60+ source voices, deterministic synthetic sample placement, and CHiME-6 train/development-informed timing statistics. They are not spontaneous conversations.

## Inputs

- Frozen V1 protocol: `benchmarks/stage11/controlled_diarization_v1`
- Common Voice 60+ source protocol: `benchmarks/speaker_breadth/commonvoice_60plus_v1`
- CHiME-6 normalized train/development metadata under `JP_DATA_ROOT/Normalized Metadata/CHiME_6`
- Existing local Pyannote, Sherpa, WeSpeaker, ReDimNet2-B2, and SpeechBrain ECAPA model assets/environments
- Runtime config: `configs/automated_evaluation/diarization_product_v2.development.yaml`

No model or dataset download is allowed.

## Outputs

- Protocol: `benchmarks/stage11/diarization_product_v2`
- Generated WAV (excluded from Git): `JustPeachyGeneratedData/diarization_product_v2`
- Development results/cache/progress: `JustPeachyResults/diarization_product_v2_development`
- Analysis: `JustPeachyResults/diarization_product_v2_development/analysis`
- Frozen decision: `JustPeachyResults/diarization_product_v2_development/frozen_diarization_development_selection.yaml`
- Compact package: `JustPeachyResearchSummaries/diarization_product_v2_development_<protocol>.zip`

Raw datasets, generated WAV, embeddings, caches, and model weights are excluded from the compact package.

The analysis retains not-reached clean-evidence observations as censored failures, reports successful-only latency separately from a conservative restricted-time lower bound, and generates 1,000-repetition confidence intervals by resampling global-speaker clusters (seed 3800). Case runners sample peak RSS for the case process plus recursive component children where `psutil` is available; early restart-reused results without this additive telemetry remain explicitly missing rather than imputed.

## PowerShell (recommended)

From PowerShell or Anaconda Prompt with PowerShell available:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy"
$Runner = "Software Validation from Datasets\Evaluation Tool\scripts\run_diarization_product_v2.ps1"

powershell -ExecutionPolicy Bypass -File $Runner -Action Audit
powershell -ExecutionPolicy Bypass -File $Runner -Action Validate
powershell -ExecutionPolicy Bypass -File $Runner -Action Plan
powershell -ExecutionPolicy Bypass -File $Runner -Action Smoke
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -ParallelPipelines 2 -OpenMonitor
```

For a terminal-independent long run, add `-Background`. The wrapper starts a hidden controller, prints its PID, and redirects its console streams under the development result root; the ordinary read-only monitor remains separate:

```powershell
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -ParallelPipelines 3 -Background
```

Read-only monitoring, status, graceful stop, restart, analysis, and collection:

```powershell
$Monitor = "Software Validation from Datasets\Evaluation Tool\scripts\monitor_diarization_product_v2.ps1"
powershell -ExecutionPolicy Bypass -File $Monitor -Follow -IntervalSeconds 30
powershell -ExecutionPolicy Bypass -File $Runner -Action Status
powershell -ExecutionPolicy Bypass -File $Runner -Action Stop
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -ParallelPipelines 2
powershell -ExecutionPolicy Bypass -File $Runner -Action Analyze
powershell -ExecutionPolicy Bypass -File $Runner -Action Collect
```

`Run` is restart-safe: checksum-valid case results are reused, invalid/partial attempts are preserved, and the shared Pyannote segmentation/window cache is reused by WeSpeaker, ReDimNet2, and SpeechBrain. `Stop` takes effect between cases. Ctrl+C in the monitor stops only the monitor.

Primary pipeline concurrency uses directly polled subprocesses rather than an in-process thread pool. This keeps progress/ETA refresh independent of backend runtimes and lets graceful stop wait for atomic case completion without a thread-pool shutdown deadlock.

## Anaconda Prompt / direct Python

No Conda environment activation is required because the controller explicitly invokes the repository management environment and each validated backend environment. From Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"..\..\.venv\Scripts\python.exe" run_evaluation.py diarization-product-v2 audit
"..\..\.venv\Scripts\python.exe" run_evaluation.py diarization-product-v2 plan
"..\..\.venv\Scripts\python.exe" run_evaluation.py diarization-product-v2 run --parallel-pipelines 2
"..\..\.venv\Scripts\python.exe" run_evaluation.py diarization-product-v2 status
```

## Actions

- `Audit`: source/protocol/pipeline readiness without evaluation inference.
- `Prepare`: deterministic V2 generation or checksum-bound reuse.
- `Validate`: V1+V2 split, clip, recipe, hash, RTTM/UEM, and firewall checks.
- `Plan`: exact units/audio/cache/reuse plus labeled runtime estimate.
- `Smoke`: one non-scientific case for each new modular pipeline and cache-reuse evidence.
- `Run`: development calibration, V1+V2 development, bounded oracle diagnostics, analysis, automatic selection, freeze, and compact collection.
- `Status`: read-only controller/progress/result snapshot.
- `Stop`: graceful stop between cases.
- `Analyze`: re-run development-only metrics/selection after results are complete.
- `Collect`: rebuild the compact ZIP without audio, caches, or weights.

The later Task 2 must verify the decision checksum and `EVALUATION_NOT_INSPECTED: true` before any controlled evaluation is authorized.

## Native campaign controller

The additive native controller is environment-aware and supports `Audit`, `Plan`, `Validate`, `Smoke`, `Run`, `Status`, `Stop`, `Analyze`, and `Collect`. Task 1 invokes only a two-unit engineering smoke (one CHiME-6 unit with DER/JER and one VOiCES fragmentation unit with DER/JER suppressed). The full native finalist campaign is reserved for Task 2.

```powershell
$Native = "Software Validation from Datasets\Evaluation Tool\scripts\run_diarization_native_campaign.ps1"
powershell -ExecutionPolicy Bypass -File $Native -Action Audit
powershell -ExecutionPolicy Bypass -File $Native -Action Plan
powershell -ExecutionPolicy Bypass -File $Native -Action Validate
powershell -ExecutionPolicy Bypass -File $Native -Action Smoke
powershell -ExecutionPolicy Bypass -File $Native -Action Status
```

An explicitly filtered future queue uses, for example, `-Action Run -Dataset chime6 -Backend sherpa_onnx_diarization -MaxUnits 5`. Omit `-MaxUnits` only when the later frozen finalist task authorizes the intended native scope.
