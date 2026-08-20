# Stage 11 Diarization and Native-Condition Evaluation

## Purpose

This package runs authorized diarization backends on immutable AMI, CHiME-6, and VOiCES native-condition scoring units. It writes strict RTTM/UEM artifacts, preserves source timing and stream/device provenance, records the segmentation source that actually controlled the output, validates reference/prediction alignment, and computes permutation-aware DER/JER only when the reference pair is scientifically compatible.

The package is additive. It uses the existing normalized metadata, Stage 2 benchmark manifests, component catalog, component YAML files, audio loader, and diarization adapters. It does not apply noise or RIR simulation to native data, acquire credentials, download models, rename anonymous clusters as reference speakers, or change existing GUI/CLI runner behavior.

## Current backend status

- `sherpa_onnx_diarization`: qualified and runnable from the existing `onnx` Stage 8 environment with local models.
- `pyannote_community`: its official gated Community-1 snapshot is installed and passes bounded software qualification in `credential-diarization`, but the frozen Stage 11 authorization registry still excludes it pending a separate scientific authorization update.
- `picovoice_falcon`: excluded until its licence action, AccessKey, package, and requalification are complete.
- `nemo_diarization`: excluded on this Windows host; it requires the planned Linux/CUDA environment, local configuration/models, and requalification.

Four modular engineering paths are also installed and bounded-smoke-qualified outside the frozen Stage 11 campaign registry:

- `modular_energy_campplus`: energy speech regions -> existing CAM++ -> deterministic average-link cosine clustering;
- `modular_pyannote_campplus`: pyannote segmentation-3.0 -> existing CAM++ -> clustering;
- `modular_pyannote_eres2net`: pyannote segmentation-3.0 -> existing ERes2Net Base -> clustering;
- `modular_energy_wespeaker`: energy speech regions -> the exact Stage 10 WeSpeaker ResNet221-LM -> clustering.

Each configuration owns a distinct engineering clustering policy ID and threshold. These thresholds are not Stage 10 recognition thresholds and have not been scientifically tuned. Outputs remain anonymous `speaker_XX` labels. A future pyannote segmentation -> ReDimNet2-B2 path needs only a new component fragment plus qualification; the modular implementation is embedding-backend agnostic.

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

Install the isolated credential-gated profile and materialize the accepted pyannote snapshots after an interactive login:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile credential-diarization
".stage8-envs\credential-diarization\Scripts\hf.exe" auth login
".stage8-envs\credential-diarization\Scripts\python.exe" "Software Validation from Datasets\Evaluation Tool\scripts\bootstrap_models.py" --pyannote
```

Paste the token only into the official interactive login prompt. Never place it in YAML, JSON, source, a command-line argument, or Git. Acquisition needs accepted Hugging Face terms and stored login; offline inference uses the pinned local snapshots with downloads disabled.

The modular configurations accept canonical repository audio and output a list of anonymous speaker-turn regions. Bounded qualification can be repeated per isolated profile without launching Stage 11:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"..\..\.stage8-envs\onnx\Scripts\python.exe" scripts\qualify_extended_backends.py --profile onnx --backend sherpa_onnx_diarization --backend campplus_speaker_embedding --backend eres2net_base_speaker_embedding --backend modular_energy_campplus
"..\..\.stage8-envs\wespeaker\Scripts\python.exe" scripts\qualify_extended_backends.py --profile wespeaker --backend wespeaker --backend modular_energy_wespeaker
"..\..\.stage8-envs\credential-diarization\Scripts\python.exe" scripts\qualify_extended_backends.py --profile credential-diarization --backend pyannote_community --backend modular_pyannote_campplus --backend modular_pyannote_eres2net
```

These commands load only the configured models and small qualification fixture. They do not compute DER/JER and do not authorize or start a Stage 11 campaign.

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
