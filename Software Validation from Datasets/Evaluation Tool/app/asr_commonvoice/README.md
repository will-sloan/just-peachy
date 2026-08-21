# Common Voice 60+ ASR generalization campaign

## Purpose

This package evaluates exactly three previously qualified ASR components—Original
Sherpa (`sherpa_onnx`), Sherpa Giga
(`sherpa_onnx_libri_giga_zipformer_2023_06_21`), and Whisper Small
(`whisper_small`)—on the exact model-independent 11,685-clip selection frozen by
`commonvoice_60plus_v1_27e72793b4c0`. It does not train, tune, download, augment,
or alter a model, checkpoint, source dataset, speaker-breadth identity, or prior
result.

The scientific unit is one unmodified Common Voice clip. The independent variable
is the ASR component. The runner defaults to sequential components, while the
PowerShell wrapper can safely run up to three isolated model processes with
`-ParallelModels`; it never loads incompatible environments into one process.
Every backend atomically checkpoints one JSON file per clip.

## Inputs

- Frozen breadth source: `benchmarks/speaker_breadth/commonvoice_60plus_v1`
- Derived ASR protocol: `benchmarks/asr_commonvoice/commonvoice_60plus_asr_v1`
- Campaign config: `configs/automated_evaluation/asr_commonvoice_60plus.v1.yaml`
- Raw assets resolved by `JP_DATA_ROOT` from the logical `Raw Datasets (Not formatted)/Common Voice/...` paths
- Existing model assets and the registered `core-cpu` and `onnx` environments

No raw contributor ID is published. Speaker IDs remain the frozen pseudonyms.

## Run from PowerShell or Anaconda Prompt

Open PowerShell, Windows Terminal, or an Anaconda Prompt. An activated Conda
environment is not required because the wrapper selects the repository's exact
Python environments. Run:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy"
$Runner = "Software Validation from Datasets\Evaluation Tool\scripts\run_asr_commonvoice_60plus.ps1"
powershell -ExecutionPolicy Bypass -File $Runner -Action Audit
powershell -ExecutionPolicy Bypass -File $Runner -Action Prepare
powershell -ExecutionPolicy Bypass -File $Runner -Action Validate
powershell -ExecutionPolicy Bypass -File $Runner -Action Plan
```

The bounded, isolated smoke (nine clips, all models) is:

```powershell
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -Smoke
powershell -ExecutionPolicy Bypass -File $Runner -Action Analyze -Smoke
powershell -ExecutionPolicy Bypass -File $Runner -Action Collect -Smoke
```

Do not use smoke outputs for scientific claims. The full run is intentionally not
started during implementation:

```powershell
powershell -ExecutionPolicy Bypass -File $Runner -Action Run
```

On the 8-core/16-thread evaluation host, use two concurrent model processes as
the conservative accelerated setting. Registered per-model inference threading
is unchanged. Accuracy/scoring remains comparable, but resource/RTF evidence is
explicitly marked as concurrent and must not be interpreted as isolated-model
performance. `-AutoExport` runs Analyze and Collect only after all three backends
finish successfully:

```powershell
powershell -ExecutionPolicy Bypass -File $Runner -Action Run -ParallelModels 2 -AutoExport
```

The same commands work when pasted into Anaconda Prompt by prefixing them with
`powershell -ExecutionPolicy Bypass -File ...`. For direct command-line diagnostics,
use the management environment:

```powershell
.\.venv\Scripts\python.exe "Software Validation from Datasets\Evaluation Tool\run_evaluation.py" asr-commonvoice plan
```

## Actions

- `Audit`: decodes selected paths and checks English, nonblank, hash-matched references; no inference.
- `Prepare`: atomically freezes or validates the model-independent ASR manifest.
- `Plan`: prints identities, population, paths, environments, and reusable result state; no inference.
- `Validate`: checks protocol/source/reference/model/environment prerequisites.
- `Run`: runs Original Sherpa, Sherpa Giga, then Whisper Small; complete valid results are reused.
- `Status`: read-only progress/result status.
- `Analyze`: writes paired and subgroup evidence after all three results validate.
- `Collect`: writes a checksummed compact directory and optional ZIP without audio or model weights.

Use `scripts/monitor_asr_commonvoice_60plus.ps1` in a second window. It only reads
progress/result files. `Ctrl+C` stops the monitor, not the campaign.

## Outputs

Scientific results use the current `evaluation_output_root("results")` location:

`JustPeachyResults/asr_commonvoice/commonvoice_60plus_asr_v1/<campaign-id>/<component>/`

Smoke results use the separate `JustPeachyResults/asr_commonvoice_smoke/...` tree.
Each backend has exact identity/config artifacts, atomic item checkpoints,
predictions, Parquet utterance results, progress, summary, and validation.

Analysis writes CSV and Parquet tables for overall, utterance, speaker, age,
duration, transcript length, error components, resources, reliability, paired
speaker-cluster bootstrap results, and deterministic error examples. Collection
writes the requested uppercase summary/inventory files, all analysis evidence,
backend predictions/config/validation, a checksum manifest, and optionally one ZIP.

## Normalization and interpretation

The existing punctuation-insensitive Evaluation Tool policy is applied identically
to references and hypotheses: lowercase; remove ASCII punctuation (including
apostrophes and hyphens); trim; collapse whitespace. Numbers remain lexical text.
Punctuation around non-speech tokens is removed, but their lexical content is not
silently discarded. Raw and normalized hypotheses are both retained.

Common Voice is primarily prompted/read speech; devices and acoustics vary; age is
self-reported categorical metadata; and this cohort may not represent product
users. This does not measure XVF3800 far-field performance or conversational
overlap and does not replace prior ASR analysis. Compare resource results only on
equivalent hosts and devices.
