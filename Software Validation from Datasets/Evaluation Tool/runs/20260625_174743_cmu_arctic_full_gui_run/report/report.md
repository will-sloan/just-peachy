# Evaluation Report

- Run folder: `20260625_174743_cmu_arctic_full_gui_run`
- Selected recordings: `1000`
- Prediction rows: `1000`
- Processed predictions: `1000`
- Missing predictions: `0`
- Missing prediction rate: `0.0000`
- Aggregate WER: `1.0003`
- Mean per-recording WER: `1.0025`
- Reference words: `8827`
- Errors: `8830`
- Substitutions: `2997`
- Insertions: `3`
- Deletions: `5830`
- Speaker label accuracy: `0.0000`
- Speaker labels scored: `1000`
- Total duration sec: `3441.8453`

## Worst Recordings

| recording_id | WER | errors | missing |
|---|---:|---:|---:|
| CMU_ARCTIC_aew_arctic_a0484 | 3.0000 | 3 | False |
| CMU_ARCTIC_aew_arctic_a0329 | 1.5000 | 3 | False |
| CMU_ARCTIC_aew_arctic_a0011 | 1.0000 | 13 | False |
| CMU_ARCTIC_aew_arctic_a0022 | 1.0000 | 13 | False |
| CMU_ARCTIC_aew_arctic_a0023 | 1.0000 | 13 | False |
| CMU_ARCTIC_aew_arctic_a0024 | 1.0000 | 13 | False |
| CMU_ARCTIC_aew_arctic_a0043 | 1.0000 | 13 | False |
| CMU_ARCTIC_aew_arctic_a0094 | 1.0000 | 13 | False |
| CMU_ARCTIC_aew_arctic_a0095 | 1.0000 | 13 | False |
| CMU_ARCTIC_aew_arctic_a0096 | 1.0000 | 13 | False |

## Accent Group Summary

| accent_group | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| native_us | 1000 | 3441.8453 | 1.0003 | 2997 | 3 | 5830 | 0 |

## Accent Summary

| accent | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| US English | 1000 | 3441.8453 | 1.0003 | 2997 | 3 | 5830 | 0 |

## Augmentation Condition Id Summary

| augmentation_condition_id | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 1000 | 3441.8453 | 1.0003 | 2997 | 3 | 5830 | 0 |

## Augmentation Mode Summary

| augmentation_mode | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | 1000 | 3441.8453 | 1.0003 | 2997 | 3 | 5830 | 0 |

## Gender Summary

| gender | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| male | 1000 | 3441.8453 | 1.0003 | 2997 | 3 | 5830 | 0 |

## Speaker Variant Group Summary

| speaker_variant_group | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| additional | 1000 | 3441.8453 | 1.0003 | 2997 | 3 | 5830 | 0 |

## Files

- `predictions/utterances.jsonl`
- `metrics/per_recording_metrics.csv`
- `metrics/aggregate_metrics.json`
- `metrics/missing_predictions.csv`
- `metrics/speaker_label_confusion.csv` when speaker-attributed predictions are scored
- `metrics/segment_speaker_metrics.csv` when `predictions/segments.rttm` exists
- `plots/`
