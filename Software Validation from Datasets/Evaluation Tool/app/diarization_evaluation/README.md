# Stage 11 Diarization and Native-Condition Evaluation

## Purpose

This package runs authorized diarization backends on immutable AMI, CHiME-6, and VOiCES native-condition scoring units. It writes strict RTTM/UEM artifacts, preserves source timing and stream/device provenance, records the segmentation source that actually controlled the output, validates reference/prediction alignment, and computes permutation-aware DER/JER only when the reference pair is scientifically compatible.

The package is additive. It uses the existing normalized metadata, Stage 2 benchmark manifests, component catalog, component YAML files, audio loader, and diarization adapters. It does not apply noise or RIR simulation to native data, acquire credentials, download models, rename anonymous clusters as reference speakers, or change existing GUI/CLI runner behavior.

## Current backend status

- `sherpa_onnx_diarization`: qualified and runnable from the existing `onnx` Stage 8 environment with local models.
- `pyannote_community`: excluded until its gated-model licence action, credential, package, local asset bootstrap, and requalification are complete.
- `picovoice_falcon`: excluded until its licence action, AccessKey, package, and requalification are complete.
- `nemo_diarization`: excluded on this Windows host; it requires the planned Linux/CUDA environment, local configuration/models, and requalification.

The `status` command reports environment-variable presence as booleans only. It never records credential values. A frozen non-qualified status cannot be bypassed merely by setting an environment variable.

## Inputs

- `benchmarks/v1/<tier>_source_manifest.parquet` from Stage 2.
- `configs/automated_evaluation/diarization_evaluation.v1.yaml`.
- `configs/automated_evaluation/extended_qualification_registry.v1.yaml`.
- Existing component fragments under `configs/inference/components/diarization/`.
- Normalized AMI and CHiME-6 timing metadata and locally available source audio.

AMI array and CHiME-6 far-field units use multi-speaker aligned references. Close-talk units use wearer-only timing and are explicitly labelled as single-speaker references. VOiCES is retained for native condition diagnostics, but DER/JER is suppressed because the repository has no compatible fine-grained speech timing for those files.

## Outputs

Immutable scoring views are stored under `benchmarks/stage11/<tier>/`:

- `native_diarization_manifest.parquet` and its versioned index/checksum;
- `references.rttm`;
- `scored_regions.uem`;
- `reference_transcripts.jsonl` for conditionally valid attributed-text work.

One execution result contains:

- `run.json`, backend status, and resolved component/model identities;
- anonymous `predictions/segments.rttm`;
- the exact reference RTTM and UEM slice;
- alignment and segmentation-provenance diagnostics;
- metrics with explicit collar, overlap, reference, speaker-count, and scoring-policy identities;
- JSON and Markdown scenario reports;
- SHA-256 checksums.

`predictions/speaker_attributed_transcript.jsonl` is conditional. The standalone diarization runner does not create it because it does not run ASR. It may be produced later only by a real composed pipeline with compatible ASR output.

## Anaconda Prompt / Command Prompt

Open Anaconda Prompt and run:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"

rem Build and validate immutable native scoring views
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization build-manifest --tier small
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization build-manifest --tier standard
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization build-manifest --tier large
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization validate --manifest-root benchmarks\stage11\small

rem Inspect every backend without exposing credentials
"C:\Users\amiri\Documents\GitHub\just-peachy\.stage8-envs\onnx\Scripts\python.exe" run_evaluation.py diarization status

rem Run the qualified real native smoke
"C:\Users\amiri\Documents\GitHub\just-peachy\.stage8-envs\onnx\Scripts\python.exe" run_evaluation.py diarization smoke --manifest-root benchmarks\stage11\small
```

Run one explicit unit after obtaining its ID from the manifest:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.stage8-envs\onnx\Scripts\python.exe" run_evaluation.py diarization run ^
  --manifest-root benchmarks\stage11\small ^
  --evaluation-unit-id diar_0123456789ab ^
  --backend sherpa_onnx_diarization ^
  --output-root runs\diarization_evaluation\scenario_0123456789ab
```

The optional `--oracle-speaker-count-diagnostic` changes the speaker-count mode and is labelled diagnostic. Do not merge it with estimated-speaker-count results.

Result folders are immutable once non-empty. To repeat or change a run, choose a fresh short result folder; in-place replacement is deliberately prohibited so old and new evidence cannot form a mixed bundle.

Aggregate independently completed result folders:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" run_evaluation.py diarization aggregate ^
  --results-root runs\diarization_evaluation ^
  --output-root runs\diarization_evaluation\analysis
```

## PowerShell

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.stage8-envs\onnx\Scripts\python.exe" run_evaluation.py diarization smoke --manifest-root benchmarks\stage11\small
```

## Tests

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest tests\automated_evaluation\test_stage11_diarization.py -q --basetemp=.pytest-stage11
```

Automated tests use synthetic RTTM fixtures and never require credentials, downloads, or a GPU. The real smoke is run separately from the qualified ONNX environment and is preserved under `runs/diarization_evaluation/`.
