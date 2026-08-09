# Evaluation Report

- Run folder: `20260806_204414_cmu_arctic_full_stage1_whisper_tiny`
- Selected recordings: `1`
- Prediction rows: `1`
- Processed predictions: `1`
- Missing predictions: `0`
- Missing prediction rate: `0.0000`
- Aggregate WER: `0.0000`
- Mean per-recording WER: `0.0000`
- Reference words: `8`
- Errors: `0`
- Substitutions: `0`
- Insertions: `0`
- Deletions: `0`
- Speaker label accuracy: `0.0000`
- Speaker labels scored: `1`
- Total duration sec: `3.8801`

## Worst Recordings

| recording_id | WER | errors | missing |
|---|---:|---:|---:|
| CMU_ARCTIC_aew_arctic_a0001 | 0.0000 | 0 | False |

## Accent Group Summary

| accent_group | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| native_us | 1 | 3.8801 | 0.0000 | 0 | 0 | 0 | 0 |

## Accent Summary

| accent | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| US English | 1 | 3.8801 | 0.0000 | 0 | 0 | 0 | 0 |

## Augmentation Condition Id Summary

| augmentation_condition_id | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 1 | 3.8801 | 0.0000 | 0 | 0 | 0 | 0 |

## Augmentation Mode Summary

| augmentation_mode | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| none | 1 | 3.8801 | 0.0000 | 0 | 0 | 0 | 0 |

## Gender Summary

| gender | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| male | 1 | 3.8801 | 0.0000 | 0 | 0 | 0 | 0 |

## Speaker Variant Group Summary

| speaker_variant_group | files | duration sec | aggregate WER | substitutions | insertions | deletions | missing |
|---|---:|---:|---:|---:|---:|---:|---:|
| additional | 1 | 3.8801 | 0.0000 | 0 | 0 | 0 | 0 |

## Files

- `predictions/utterances.jsonl`
- `metrics/per_recording_metrics.csv`
- `metrics/aggregate_metrics.json`
- `metrics/missing_predictions.csv`
- `metrics/speaker_label_confusion.csv` when speaker-attributed predictions are scored
- `metrics/segment_speaker_metrics.csv` when `predictions/segments.rttm` exists
- `plots/`
