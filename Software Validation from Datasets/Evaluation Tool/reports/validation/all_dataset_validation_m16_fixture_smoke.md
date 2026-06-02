# All-Dataset Validation Report

## Milestone

M16 - All-Dataset and All-Augmentation Validation Battery

## Sweep Config Used

- Run id: `m16_fixture_smoke`
- Sweep: `all_datasets_smoke`
- Config path: `configs/sweeps/all_datasets_smoke.yaml`
- Dry fixture mode: `True`
- Started at: `2026-06-02T16:53:00+00:00`
- Wall duration seconds: `0.025`
- Machine-readable JSON: `reports/validation/all_dataset_validation_m16_fixture_smoke.json`
- Machine-readable CSV: `reports/validation/all_dataset_validation_m16_fixture_smoke.csv`

## Datasets Attempted

- CMU Arctic (`cmu_arctic`): 1 job(s)
- LibriSpeech (`librispeech`): 1 job(s)
- HiFiTTS (`hifitts`): 1 job(s)
- AMI Meeting Corpus (`ami`): 1 job(s)
- VOiCES DevKit (`voices`): 1 job(s)
- CHiME-6 (`chime6`): 1 job(s)

## Dataset Availability And Blockers

- Full real all-dataset execution was not attempted in dry fixture mode.

## Generated Run Folders

- `cmu_arctic_clean` (succeeded): `runs/all_dataset_validation/m16_fixture_smoke/cmu_arctic_clean/m16_fixture_smoke_cmu_arctic_clean`
- `librispeech_clean` (succeeded): `runs/all_dataset_validation/m16_fixture_smoke/librispeech_clean/m16_fixture_smoke_librispeech_clean`
- `hifitts_clean` (succeeded): `runs/all_dataset_validation/m16_fixture_smoke/hifitts_clean/m16_fixture_smoke_hifitts_clean`
- `ami_native_meeting` (succeeded): `runs/all_dataset_validation/m16_fixture_smoke/ami_native_meeting/m16_fixture_smoke_ami_native_meeting`
- `voices_native_farfield` (succeeded): `runs/all_dataset_validation/m16_fixture_smoke/voices_native_farfield/m16_fixture_smoke_voices_native_farfield`
- `chime6_native_farfield` (succeeded): `runs/all_dataset_validation/m16_fixture_smoke/chime6_native_farfield/m16_fixture_smoke_chime6_native_farfield`

## Cross-Dataset Comparison

| Dataset | Runs | WER | CER | Speaker accuracy | Missing rate | Crash/timeout rate | RTF | Memory MB | Failure modes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| cmu_arctic | 1 | 0.1667 | n/a | 0.5000 | 0.0000 | 0.0000 | 0.2500 | 256.0000 | none |
| librispeech | 1 | 0.3333 | n/a | 0.5000 | 0.0000 | 0.0000 | 0.2500 | 256.0000 | none |
| hifitts | 1 | 0.1667 | n/a | 0.5000 | 0.0000 | 0.0000 | 0.2500 | 256.0000 | none |
| ami | 1 | 0.3333 | n/a | 0.5000 | 0.0000 | 0.0000 | 0.2500 | 256.0000 | none |
| voices | 1 | 0.1667 | n/a | 0.5000 | 0.0000 | 0.0000 | 0.2500 | 256.0000 | none |
| chime6 | 1 | 0.3333 | n/a | 0.5000 | 0.0000 | 0.0000 | 0.2500 | 256.0000 | none |

## Augmentation And Native-Condition Breakdown

| Job | Dataset | Condition | Augmentation | Native condition | SNR | Noise | Status | WER | Missing rate | Device |
| --- | --- | --- | --- | --- | ---: | --- | --- | ---: | ---: | --- |
| cmu_arctic_clean | cmu_arctic | clean | none | False | n/a | n/a | succeeded | 0.1667 | 0.0000 | cpu |
| librispeech_clean | librispeech | clean | none | False | n/a | n/a | succeeded | 0.3333 | 0.0000 | cpu |
| hifitts_clean | hifitts | clean | none | False | n/a | n/a | succeeded | 0.1667 | 0.0000 | cpu |
| ami_native_meeting | ami | native_meeting | none | True | n/a | n/a | succeeded | 0.3333 | 0.0000 | cpu |
| voices_native_farfield | voices | native_farfield | none | True | n/a | n/a | succeeded | 0.1667 | 0.0000 | cpu |
| chime6_native_farfield | chime6 | native_farfield | none | True | n/a | n/a | succeeded | 0.3333 | 0.0000 | cpu |

## CMU Arctic (`cmu_arctic`)

### clean

- Status: `succeeded`
- Run folder: `runs/all_dataset_validation/m16_fixture_smoke/cmu_arctic_clean/m16_fixture_smoke_cmu_arctic_clean`
- Failure mode: `none`
- WER: `0.1667`
- CER: `n/a`
- Speaker label accuracy: `0.5000`
- Missing predictions: `0.0000`
- Missing prediction rate: `0.0000`
- Runtime device: `cpu`
- Realtime factor: `0.2500`
- Memory peak MB: `256.0000`
- Stutter/repetition rate: `0.1429`
- Model identifiers: `{"asr": "m16-fixture-asr@1", "runner": "simulation", "speaker_matching": "m16-fixture-speaker@1"}`

## LibriSpeech (`librispeech`)

### clean

- Status: `succeeded`
- Run folder: `runs/all_dataset_validation/m16_fixture_smoke/librispeech_clean/m16_fixture_smoke_librispeech_clean`
- Failure mode: `none`
- WER: `0.3333`
- CER: `n/a`
- Speaker label accuracy: `0.5000`
- Missing predictions: `0.0000`
- Missing prediction rate: `0.0000`
- Runtime device: `cpu`
- Realtime factor: `0.2500`
- Memory peak MB: `256.0000`
- Stutter/repetition rate: `0.1429`
- Model identifiers: `{"asr": "m16-fixture-asr@1", "runner": "simulation", "speaker_matching": "m16-fixture-speaker@1"}`

## HiFiTTS (`hifitts`)

### clean

- Status: `succeeded`
- Run folder: `runs/all_dataset_validation/m16_fixture_smoke/hifitts_clean/m16_fixture_smoke_hifitts_clean`
- Failure mode: `none`
- WER: `0.1667`
- CER: `n/a`
- Speaker label accuracy: `0.5000`
- Missing predictions: `0.0000`
- Missing prediction rate: `0.0000`
- Runtime device: `cpu`
- Realtime factor: `0.2500`
- Memory peak MB: `256.0000`
- Stutter/repetition rate: `0.1429`
- Model identifiers: `{"asr": "m16-fixture-asr@1", "runner": "simulation", "speaker_matching": "m16-fixture-speaker@1"}`

## AMI Meeting Corpus (`ami`)

### native_meeting

- Status: `succeeded`
- Run folder: `runs/all_dataset_validation/m16_fixture_smoke/ami_native_meeting/m16_fixture_smoke_ami_native_meeting`
- Failure mode: `none`
- WER: `0.3333`
- CER: `n/a`
- Speaker label accuracy: `0.5000`
- Missing predictions: `0.0000`
- Missing prediction rate: `0.0000`
- Runtime device: `cpu`
- Realtime factor: `0.2500`
- Memory peak MB: `256.0000`
- Stutter/repetition rate: `0.1429`
- Model identifiers: `{"asr": "m16-fixture-asr@1", "runner": "simulation", "speaker_matching": "m16-fixture-speaker@1"}`

## VOiCES DevKit (`voices`)

### native_farfield

- Status: `succeeded`
- Run folder: `runs/all_dataset_validation/m16_fixture_smoke/voices_native_farfield/m16_fixture_smoke_voices_native_farfield`
- Failure mode: `none`
- WER: `0.1667`
- CER: `n/a`
- Speaker label accuracy: `0.5000`
- Missing predictions: `0.0000`
- Missing prediction rate: `0.0000`
- Runtime device: `cpu`
- Realtime factor: `0.2500`
- Memory peak MB: `256.0000`
- Stutter/repetition rate: `0.1429`
- Model identifiers: `{"asr": "m16-fixture-asr@1", "runner": "simulation", "speaker_matching": "m16-fixture-speaker@1"}`

## CHiME-6 (`chime6`)

### native_farfield

- Status: `succeeded`
- Run folder: `runs/all_dataset_validation/m16_fixture_smoke/chime6_native_farfield/m16_fixture_smoke_chime6_native_farfield`
- Failure mode: `none`
- WER: `0.3333`
- CER: `n/a`
- Speaker label accuracy: `0.5000`
- Missing predictions: `0.0000`
- Missing prediction rate: `0.0000`
- Runtime device: `cpu`
- Realtime factor: `0.2500`
- Memory peak MB: `256.0000`
- Stutter/repetition rate: `0.1429`
- Model identifiers: `{"asr": "m16-fixture-asr@1", "runner": "simulation", "speaker_matching": "m16-fixture-speaker@1"}`

## Failure-Mode Classification

| Job | Status | Failure mode | Blocker |
| --- | --- | --- | --- |
| cmu_arctic_clean | succeeded | none | n/a |
| librispeech_clean | succeeded | none | n/a |
| hifitts_clean | succeeded | none | n/a |
| ami_native_meeting | succeeded | none | n/a |
| voices_native_farfield | succeeded | none | n/a |
| chime6_native_farfield | succeeded | none | n/a |

## Recommendations

- Run the same sweep without --dry-run-fixtures once all six dataset assets and model dependencies are available.

## Exact Commands

### Tests

- `cd "/Users/billy/Documents/just-peachy" && source .venv/bin/activate && python -m pytest "Software Validation from Datasets/Evaluation Tool/tests/inference_pipeline/test_all_dataset_validation.py"`
- `cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool" && source "/Users/billy/Documents/just-peachy/.venv/bin/activate" && python -m pytest tests`

### Smoke Checks

- `cd "/Users/billy/Documents/just-peachy" && source .venv/bin/activate && python "Software Validation from Datasets/Evaluation Tool/scripts/run_all_dataset_validation.py" --run-id m16_fixture_smoke --sweep-config "Software Validation from Datasets/Evaluation Tool/configs/sweeps/all_datasets_smoke.yaml" --dry-run-fixtures`

## Incomplete Or Blocked

- Dry fixture mode validates sweep parsing, aggregation, and reporting only; full real dataset/model execution was not performed.
