# Training Tool: Phase-2 data freeze

## Purpose

This additive tool freezes a local inventory of speech metadata, licence/provenance policy, and an evaluation-leakage firewall. It is a research/compliance aid, not legal advice. It never decodes audio, downloads data, installs Icefall, trains a model, changes the Evaluation Tool, or creates train/dev/test splits.

The existing Just-Peachy evaluation universe remains test-only. Future training-manifest work must select from this registry rather than move or regenerate evaluation data.

## Inputs

- Normalized metadata and local licence files below `JP_DATA_ROOT` (default: `Software Validation from Datasets`).
- Every benchmark parquet beneath `Evaluation Tool/benchmarks` that has source identities. This includes the v1 Small, Standard, Large, speaker-protocol, and later source-identified benchmark material.
- [license_policy.v1.json](training_data/license_policy.v1.json), the versioned policy and evidence record.

The CMU Arctic entry is CC0-1.0 based on an operator-supplied local classification. Local files independently verify the LibriSpeech, HiFiTTS, and CHiME-6 entries. AMI preserves its locally bundled historical CC BY-NC-SA 2.5 `LICENCE.txt` as provenance, but the AMI maintainers relicensed the unchanged core corpus under CC BY 4.0 on 10 April 2017. The registry therefore uses CC BY 4.0 as AMI's effective current licence: intended-commercial training is allowed with attribution. CHiME-6 is technically eligible but review-gated; this is not a legal conclusion about model weights.

## Outputs

`build` writes ignored, machine-local outputs under `JP_TRAINING_ROOT` (default: `<repository>/training`):

- `registries/training_data_registry.parquet`: one normalized training candidate per source segment/item.
- `registries/evaluation_exclusion_index.parquet`: de-duplicated frozen evaluation identities and their benchmark references.
- `registries/*summary.json` and `training_data_freeze_manifest.json`: deterministic identities, statistics, licence-policy hash, and evaluation-manifest hashes.
- `audits/training_data_audit.json` and `audits/training_data_audit.md`: human and machine audit reports.
- `license_evidence/*.json`: compact licence/provenance records, with digests for local small licence files.

Absolute `resolved_audio_path` fields are diagnostic-only. They never participate in canonical hashes. `source_available` means the normalized metadata supplied a rebasable path; the freeze intentionally does not run a slow per-audio filesystem probe or hash raw audio.

For a policy correction, preserve the existing freeze and build to a separate successor directory with `--parent-freeze`. The successor records the parent ID and hash in its own freeze manifest.

## Run from Anaconda Prompt, Command Prompt, or PowerShell

Use the repository virtual environment (or replace its Python executable with the Python from the activated Anaconda environment). Quote the directory because it contains spaces.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m training_data.cli build
..\..\.venv\Scripts\python.exe -m training_data.cli verify-freeze
..\..\.venv\Scripts\python.exe -m training_data.cli summary
..\..\.venv\Scripts\python.exe -m training_data.cli preview-pool robust_plus_chime
```

Create the AMI CC BY 4.0 correction successor without overwriting the historical Phase-2 output:

```powershell
$parent = '..\..\training\registries\training_data_freeze_manifest.json'
$successor = '..\..\training\successors\ami_cc_by_4_0_2017_04_10'
..\..\.venv\Scripts\python.exe -m training_data.cli build --output-root $successor --parent-freeze $parent --correction-reason ami_cc_by_4_0_relicensing_2017_04_10
..\..\.venv\Scripts\python.exe -m training_data.cli verify-freeze --path "$successor\registries\training_data_freeze_manifest.json"
```

To write data and generated registries somewhere other than the checkout, set the Phase-1 resolver inputs before running:

```powershell
$env:JP_DATA_ROOT = 'D:\just-peachy-data\Software Validation from Datasets'
$env:JP_TRAINING_ROOT = 'D:\just-peachy-training'
..\..\.venv\Scripts\python.exe -m training_data.cli build
```

On Linux or WSL:

```bash
cd '/work/just-peachy/Software Validation from Datasets/Training Tool'
../../.venv/bin/python -m training_data.cli build
../../.venv/bin/python -m training_data.cli verify-freeze
```

Inspect the Phase-1 roots first with:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
..\..\.venv\Scripts\python.exe -m app.utils.paths
```

## Leakage and future selection

`relaxed_training_eligible` excludes exact evaluation items and cross-dataset source matches. `strict_training_eligible` also excludes evaluation speaker, reader, meeting, session, or VOiCES source-speaker groups, depending on the dataset. Strict is the default for future model-selection research.

VOiCES original-source identifiers are normalized to the corresponding LibriSpeech speaker/chapter/segment identity when available, so a retransmission and its direct source cannot cross the firewall. HiFiTTS and LibriSpeech share audiobook provenance, but the local metadata contains no reliable item-level crosswalk; the tool reports this limitation rather than inventing a match.

Future code can use `training_data.registry.select_records(frame, strict=True, commercial_policy='straightforward')`, or the `review_gated` policy for CHiME-6. This tool deliberately returns candidates only; it does not freeze a future split.

When Common Voice arrives, create a new additive registry/freeze version from this one plus its exact release. Do not overwrite this Phase-2 snapshot.

## Test

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m pytest -q tests
```
