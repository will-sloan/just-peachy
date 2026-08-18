# Training Tool: Phase-2 data freeze and Phase-3 acquisition gate

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

## Phase 3: pinned Common Voice English acquisition

Phase 3 pins **Common Voice Scripted Speech 26.0 - English**, locale `en`, corpus release `cv-corpus-26.0-2026-06-12`, released 2026-06-17. The official Mozilla Data Collective record identifies the dataset as `cmqim2hn800ssnr07gvmpcnwu`, licenses it under `CC0-1.0`, and publishes archive size `94,639,372,950` bytes and SHA-256 `6809228E6AB506D18F6A1EBC830056450F8266C8F513D6038BDB0FC88A49E6CB`.

The immutable release record is [common_voice_release.v1.json](training_data/common_voice_release.v1.json). [common_voice.py](training_data/common_voice.py) uses Mozilla's official `datacollective` Python SDK. The SDK resumes an interrupted download when its `.part` and `.checksum` state remain in the same directory. The wrapper refuses an unexpected filename, byte size, or SHA-256 and never stores or prints the API key.

Inputs:

- the existing `JP_TRAINING_ROOT` setting;
- an `MDC_API_KEY` supplied only through the current shell;
- the pinned Mozilla dataset ID and published archive identity.

Outputs, all ignored by Git, are beneath:

```text
<JP_TRAINING_ROOT>/datasets/common_voice/english/cv-corpus-26.0-2026-06-12/
  source/common-voice-scripted-speech-26-0-englis-c84784ae.tar.gz
  metadata/acquisition_manifest.json
```

This acquisition command does **not** extract the archive, select speakers, create splits, alter evaluation, or create a Phase-3 freeze. Those operations remain blocked until the exact archive verifies.

### One-time authenticated setup and continuation

1. Open the [official Mozilla dataset record](https://mozilladatacollective.com/datasets/cmqim2hn800ssnr07gvmpcnwu), sign in or create an account, read and accept the dataset conditions, and confirm the Common Voice prohibitions on speaker identification and redistribution.
2. In Mozilla Data Collective, open **Account -> Credentials** and create or retrieve an API key.
3. In Anaconda Prompt or PowerShell, run the following. Do not put the key in a `.env` file inside this repository and do not commit it.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m pip install datacollective
$env:MDC_API_KEY = Read-Host 'Mozilla Data Collective API key'
..\..\.venv\Scripts\python.exe -m training_data.common_voice status
..\..\.venv\Scripts\python.exe -m training_data.common_voice acquire
```

In classic Anaconda Prompt (`cmd.exe`), use `set /p MDC_API_KEY=Mozilla Data Collective API key:` instead of the PowerShell `Read-Host` line. Rerun the same `acquire` command after any interruption; the official SDK resumes automatically. After it reports `download_complete: true`, continue Phase 3 with archive extraction, real metadata/age-schema inspection, older-speaker selection, leakage checks, speaker-disjoint splits, and a successor freeze derived from `training_freeze_7a88aec7492f`.

Before authentication, the safe diagnostic command is:

```powershell
..\..\.venv\Scripts\python.exe -m training_data.common_voice status
```

### Selectively prepare an operator-downloaded archive

When the authenticated archive already exists under `JP_DATA_ROOT/Raw Datasets (Not formatted)`, it may have an operator-friendly local name such as `Common Voice.gz`. The local filename is not scientific identity: the Phase-3 workflow discovers the single size-matching file, detects gzip from its content, and accepts it only after the compressed SHA-256 exactly matches the pinned Mozilla archive.

The workflow performs two sequential archive traversals:

1. verify the complete compressed SHA-256 while indexing members and preserving the original metadata files;
2. extract every missing validated age>=60 MP3 in one streaming traversal.

It does not full-extract Common Voice and does not reopen the archive once per clip. The selected MP3s and resume state are stored beneath `JP_TRAINING_ROOT`:

```text
<JP_TRAINING_ROOT>/datasets/common_voice/english/cv-corpus-26.0-2026-06-12/prepared/en/
  metadata/original/
  metadata/derived/
  clips/
  state/
```

The additive Phase-3 registry, audits, membership manifest, license evidence, and freeze are written beneath:

```text
<JP_TRAINING_ROOT>/successors/common_voice_26_english_phase3/
```

Run from Anaconda Prompt or PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m training_data.common_voice phase3-status
..\..\.venv\Scripts\python.exe -m training_data.common_voice phase3-run
..\..\.venv\Scripts\python.exe -m training_data.common_voice phase3-verify
```

`phase3-run` is resumable. A completed source audit is reused when its pinned identity and metadata are present. During selective materialization, completed MP3s and their validation rows are reused; a rerun makes one archive pass only for missing selected members. The workflow also hashes every source-audio file referenced by the frozen evaluation exclusion index, stores a portable content-hash-index identity in the successor freeze, and caches file hashes by size and modification time for later reruns. Inputs are the verified source archive, corrected Phase-2 freeze, Phase-2 registry, evaluation exclusion index, and the evaluation audio it references. Outputs are selected original MP3s, exact original TSVs, derived Parquet registries, deterministic train/dev/heldout membership, audits, pool previews, and an immutable successor freeze. No Icefall installation, training manifest, model training, inference, or ONNX export occurs.

## Test

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m pytest -q tests
```
