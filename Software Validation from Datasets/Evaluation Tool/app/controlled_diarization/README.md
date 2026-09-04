# Controlled diarization benchmark

## Purpose

This package builds and operates `controlled_diarization_v1`, a model-independent
anonymous-speaker benchmark. It mixes complete Common Voice utterances with a
deterministic placement schedule, writes the timing reference while rendering,
and later runs selected diarization pipelines through isolated environments.
It does not identify people and it never uses reference labels to name stored
predictions.

The source voices are prompted/read speech. The turn order, gaps, and overlap
are synthetic. The RTTM is therefore an exact **synthetic placement timing
reference**, not a human frame-level speech annotation.

## Inputs

- `configs/automated_evaluation/controlled_diarization_benchmark.v1.yaml`
- an explicit frozen speaker-pool manifest; the default is
  `benchmarks/speaker_breadth/commonvoice_60plus_v1/speaker_protocol_manifest.json`
- its canonical Common Voice `validated.tsv`, `clip_durations.tsv`, and local
  clips under `JP_DATA_ROOT`
- the existing component catalog, qualified model assets, and isolated profile
  interpreters for any pipeline selected later

The generator uses the frozen Common Voice pseudonymous speaker inventory. It
does not publish raw contributor IDs. Five independent enrollment clips per
selected speaker remain reserved and cannot appear in a mixture.

## Outputs

Committed/small metadata lives under:

```text
benchmarks/stage11/controlled_diarization_v1/
```

Rendered WAV files are external and default to:

```text
<Evaluation Tool>\JustPeachyGeneratedData\controlled_diarization_v1\
```

Set `JP_GENERATED_DATA_ROOT` to move the physical generated-data base without
changing scientific identity. Results default to:

```text
<Evaluation Tool>\JustPeachyResults\diarization\controlled_diarization_v1\
```

Newly executed cases record best-effort `resource_telemetry` in `run.json`: peak RSS for the case process plus recursive component children, sampled every 0.1 seconds when `psutil` is available. Historical checksum-valid results remain reusable and may omit this additive field; analyses report that telemetry as missing rather than imputing it.

No generated WAV, Common Voice MP3, model asset, credential, or raw contributor
identity belongs in Git.

## Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py diarization-benchmark audit
python run_evaluation.py diarization-benchmark prepare
python run_evaluation.py diarization-benchmark validate
python run_evaluation.py diarization-benchmark plan --tier development --pipeline PLACEHOLDER_PIPELINE_1
```

`audit`, `prepare`, `validate`, and `plan` perform no model inference. `prepare`
reuses valid external WAVs and reconstructs only missing or changed WAVs from
the committed frozen recipes. It never silently changes the frozen manifests.

## PowerShell

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File `
  "Software Validation from Datasets\Evaluation Tool\scripts\run_controlled_diarization.ps1" `
  -Action Audit

powershell -ExecutionPolicy Bypass -File `
  "Software Validation from Datasets\Evaluation Tool\scripts\run_controlled_diarization.ps1" `
  -Action Prepare

powershell -ExecutionPolicy Bypass -File `
  "Software Validation from Datasets\Evaluation Tool\scripts\run_controlled_diarization.ps1" `
  -Action Validate
```

## Runtime pipeline IDs

| Pipeline ID | Meaning | Current interface status |
| --- | --- | --- |
| `modular_energy_campplus` | lightweight Energy VAD/windows + CAM++ + agglomerative cosine clustering | software-qualified; development calibration required |
| `modular_pyannote_campplus` | Pyannote Segmentation 3.0 + the same CAM++ + clustering family | software-qualified; development calibration required |
| `sherpa_onnx_diarization` | existing independent Sherpa-ONNX diarizer | frozen Stage 11 authorized baseline |
| `modular_energy_wespeaker` | lightweight Energy VAD/windows + WeSpeaker + clustering | software-qualified; development calibration required |
| `pyannote_community1` | complete Community-1 pipeline with its documented local default | software-qualified; default/off-the-shelf comparison |
| `oracle_turn_campplus_diagnostic` | reference turns + CAM++ + clustering | diagnostic only; non-overlap development cases |
| `modular_pyannote_selected_embedding` | future Segmentation 3.0 + selected speaker finalist | `NOT_INTEGRATED` until the finalist/configuration is frozen |

Pipeline selection is always supplied at runtime. No speaker-research winner is
hardcoded. `pipeline-status` reports exact profile/config readiness without
loading a model:

```bat
python run_evaluation.py diarization-benchmark pipeline-status
```

## Restart-safe development and evaluation

Run development only after reviewing `plan`:

```bat
python run_evaluation.py diarization-benchmark run ^
  --tier development ^
  --pipeline PLACEHOLDER_PIPELINE_1
```

Each pipeline/case runs sequentially in its declared environment. A checksum-
valid result is `REUSE`. Invalid/partial and failed attempts are preserved under
`_partial` or `_failed`; they are never treated as success. A `STOP_REQUESTED`
file is honored between cases.

After development, analyze and make an explicit operator decision. Then freeze
only the selected exact pipeline hashes:

```bat
python run_evaluation.py diarization-benchmark analyze ^
  --tier development ^
  --pipeline PLACEHOLDER_PIPELINE_1

python run_evaluation.py diarization-benchmark freeze-pipelines ^
  --pipeline PLACEHOLDER_PIPELINE_1 ^
  --decision-note "Approved after development analysis" ^
  --output C:\results\frozen_pipeline_configuration.json
```

Evaluation refuses to start without that file, the matching benchmark ID,
matching pipeline hashes, a frozen decision, and the no-evaluation-tuning flag:

```bat
python run_evaluation.py diarization-benchmark run ^
  --tier evaluation ^
  --pipeline PLACEHOLDER_PIPELINE_1 ^
  --frozen-pipeline-config C:\results\frozen_pipeline_configuration.json
```

## Analysis and collection

`analyze` creates recording-, factor-, speaker-count-, cadence-, overlap-,
fragmentation-, merge-, single-speaker-control-, re-entry-, resource-,
reliability-, oracle-, and paired comparison tables plus separate interaction
plots where results exist.
Development and evaluation are never averaged together. Oracle diagnostics are
never admitted to the primary ranking.

`collect` copies compact metadata, references, configurations, predictions,
scores, and reports. It records external audio paths and SHA-256 values in
`RESULT_FILE_INVENTORY.csv`; it does not copy the large WAV files.

## Tests

Run the focused model-free tests from the Evaluation Tool directory:

```bat
..\..\.venv\Scripts\python.exe -m pytest tests\automated_evaluation\test_controlled_diarization_benchmark.py -q --basetemp artifacts\pytest_controlled_diarization
```

They cover deterministic/disjoint speaker splits, stable pseudonyms, factorial
balance, pair auditing, recurrence/timing/overlap references, deterministic
recipe reconstruction, scenario identity, Plan, result validation,
restart/reuse, analysis output, and CLI discovery.
