# Frozen Final Standalone Diarization Evaluation

## Purpose

This package performs Task 2 of the standalone anonymous-diarization study. It validates and consumes Task 1's frozen development decision, runs only the exact frozen finalists on untouched Controlled V1 and Product V2 evaluation cases, runs a finalists-only CHiME-6 native-small reality check, and runs scientifically limited VOiCES acoustic-fragmentation diagnostics.

It never assigns real names, uses enrollment, performs known/unknown matching, runs hybrid speaker attribution, runs ASR/cpWER, downloads models, tunes against evaluation, or fine-tunes a model.

The frozen finalists are loaded from:

```text
JustPeachyResults/diarization_product_v2_development/
  frozen_diarization_development_selection.yaml
  frozen_diarization_development_selection.sha256
  frozen_development_pipeline_config.yaml
```

The controller refuses evaluation when the selection checksum, exact configuration hashes, development result identity, protocol IDs, Task-1 result-affecting code identity, or `evaluation_authorized`/`EVALUATION_NOT_INSPECTED` flags do not validate.

## Inputs

- Frozen Task-1 development selection and runtime configuration.
- Controlled V1 evaluation protocol `controlled_diarization_v1_acd5e6e431d8` and generated evaluation audio.
- Product V2 evaluation protocol `diarization_product_v2_6b6c50a5de31` and generated evaluation audio.
- Task-1 native-small manifest with all 80 CHiME-6 units and 40 VOiCES units.
- Existing local Pyannote segmentation, WeSpeaker, and ReDimNet2 model assets in their isolated environments.
- External CHiME-6 and VOiCES source audio under `JP_DATA_ROOT/Raw Datasets (Not formatted)`.

Native source files are never modified. Runtime-only, hash-bound mono 16 kHz PCM16 slices are stored under the ignored result root and excluded from export.

## Outputs

```text
JustPeachyResults/diarization_finalists_final_evaluation/
├── evaluation_authorization/       # derived gates bound to the Task-1 checksum
├── controlled_v1/evaluation/       # checksum-bound V1 results
├── controlled_v2/evaluation/       # checksum-bound V2 results
├── native/chime6/                   # native CHiME-6 finalist results
├── native/voices/                   # VOiCES diagnostics; DER/JER suppressed
├── analysis/                        # final CSV, plots, REPORT.md, METRIC_GUIDE.md
├── campaign_progress.json
├── controller_state.json
├── validation.json
└── package.json

JustPeachyResearchSummaries/
└── diarization_finalists_final_evaluation_diarization_product_v2_6b6c50a5de31.zip
```

The compact ZIP excludes raw/generated audio, model weights, embedding/segmentation caches, and preserved failed attempts.

## PowerShell

Open PowerShell at the repository root:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy"
$Runner = "Software Validation from Datasets\Evaluation Tool\scripts\run_diarization_final_evaluation.ps1"

# Validate the frozen decision without inference.
powershell -ExecutionPolicy Bypass -File $Runner -Action Validate
powershell -ExecutionPolicy Bypass -File $Runner -Action Plan

# Full restart-safe final run with two frozen pipelines and an automatic monitor.
powershell -ExecutionPolicy Bypass -File $Runner `
  -Action Run -Scope all -ParallelPipelines 2 -Background -OpenMonitor

# Read-only monitor. Ctrl+C closes only this monitor.
powershell -ExecutionPolicy Bypass -File `
  "Software Validation from Datasets\Evaluation Tool\scripts\monitor_diarization_final_evaluation.ps1" `
  -Follow -IntervalSeconds 30

# Operator controls.
powershell -ExecutionPolicy Bypass -File $Runner -Action Status
powershell -ExecutionPolicy Bypass -File $Runner -Action Stop

# Restart the identical command after interruption; valid checksum-bound units are reused.
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -Scope all -ParallelPipelines 2

# Explicit scopes use the same frozen configurations.
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -Scope controlled -ParallelPipelines 2
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -Scope chime6 -ParallelPipelines 2
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -Scope voices -ParallelPipelines 2

# Rebuild analysis or export from complete valid results.
powershell -ExecutionPolicy Bypass -File $Runner -Action Analyze
powershell -ExecutionPolicy Bypass -File $Runner -Action Collect
```

The native runner retries only the known transient Windows atomic-rename
access-denied failure, up to three attempts. Queue state records every retry;
the frozen model, configuration, inputs, scoring, and scientific outputs do not
change.

## Anaconda Prompt / Command Prompt

No environment activation is required. Call the repository management interpreter explicitly:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"

"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization-final-evaluation validate
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization-final-evaluation plan
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization-final-evaluation run --scope all --parallel-pipelines 2
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization-final-evaluation status
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization-final-evaluation stop
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization-final-evaluation analyze
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization-final-evaluation collect
```

The management interpreter launches the already-qualified isolated Pyannote, WeSpeaker, and ReDimNet2 workers. Do not install all model dependencies into one environment.

## Scientific interpretation

- Controlled primary scoring is zero-collar, UEM-bound, overlap-aware DER/JER.
- CHiME-6 follows the existing Stage 11 native 250 ms-collar policy. Forty units are far-field multi-speaker views and forty are participant-close wearer-only views; they are reported separately.
- VOiCES lacks compatible fine timing. It reports predicted speaker count, changes/minute, fragment count, largest-cluster share, phantom duration, failure rate, RTF, and RAM only.
- The monitor's ETA is calculated only from measured completed audio after the current resume. It remains `calculating` until enough new work completes.
- Desktop RTF/RAM do not imply Beaker power or thermal behavior.

## Targeted tests

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest tests\automated_evaluation\test_diarization_final_evaluation.py -q
```

Tests validate the frozen decision, native panel/reference limitations, anonymous fragmentation diagnostics, export firewall, and monitor/control surface. They do not run the complete model campaign.
