# Evaluation Report

- Run folder: `20260625_174544_cmu_arctic_full_gui_run`
- Selected recordings: `10`
- Prediction rows: `10`
- Processed predictions: `10`
- Missing predictions: `0`
- Missing prediction rate: `0.0000`
- Aggregate WER: `1.0000`
- Mean per-recording WER: `1.0000`
- Reference words: `91`
- Errors: `91`
- Substitutions: `30`
- Insertions: `0`
- Deletions: `61`
- Speaker label accuracy: `0.0000`
- Speaker labels scored: `10`
- Total duration sec: `32.8550`

## Worst Recordings

| recording_id | WER | errors | missing |
|---|---:|---:|---:|
| CMU_ARCTIC_aew_arctic_a0010 | 1.0000 | 12 | False |
| CMU_ARCTIC_aew_arctic_a0003 | 1.0000 | 11 | False |
| CMU_ARCTIC_aew_arctic_a0006 | 1.0000 | 11 | False |
| CMU_ARCTIC_aew_arctic_a0007 | 1.0000 | 11 | False |
| CMU_ARCTIC_aew_arctic_a0004 | 1.0000 | 9 | False |
| CMU_ARCTIC_aew_arctic_a0009 | 1.0000 | 9 | False |
| CMU_ARCTIC_aew_arctic_a0001 | 1.0000 | 8 | False |
| CMU_ARCTIC_aew_arctic_a0002 | 1.0000 | 8 | False |
| CMU_ARCTIC_aew_arctic_a0008 | 1.0000 | 7 | False |
| CMU_ARCTIC_aew_arctic_a0005 | 1.0000 | 5 | False |

## Accent Group Summary

| accent_group | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| native_us | 10 | 32.8550 | 1.0000 | 30 | 0 | 61 | 0 |

## Accent Summary

| accent | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| US English | 10 | 32.8550 | 1.0000 | 30 | 0 | 61 | 0 |

## Augmentation Condition Id Summary

| augmentation_condition_id | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 10 | 32.8550 | 1.0000 | 30 | 0 | 61 | 0 |

## Augmentation Mode Summary

| augmentation_mode | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | 10 | 32.8550 | 1.0000 | 30 | 0 | 61 | 0 |

## Gender Summary

| gender | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| male | 10 | 32.8550 | 1.0000 | 30 | 0 | 61 | 0 |

## Speaker Variant Group Summary

| speaker_variant_group | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| additional | 10 | 32.8550 | 1.0000 | 30 | 0 | 61 | 0 |

## Files

- `predictions/utterances.jsonl`
- `metrics/per_recording_metrics.csv`
- `metrics/aggregate_metrics.json`
- `metrics/missing_predictions.csv`
- `metrics/speaker_label_confusion.csv` when speaker-attributed predictions are scored
- `metrics/segment_speaker_metrics.csv` when `predictions/segments.rttm` exists
- `plots/`
