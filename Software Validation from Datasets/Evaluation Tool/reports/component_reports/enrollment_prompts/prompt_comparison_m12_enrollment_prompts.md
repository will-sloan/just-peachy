# Enrollment Prompt Comparison Report

## Milestone

M12 - Enrollment Prompt Testing Framework

- Run id: `m12_enrollment_prompts`
- Prompt strategies compared: `4`
- Samples evaluated: `19`

## Files Changed

- `app/inference_pipeline/enrollment/prompt_sets.yaml`
- `app/inference_pipeline/experiments/__init__.py`
- `app/inference_pipeline/experiments/enrollment_prompt_eval.py`
- `scripts/run_enrollment_prompt_eval.py`
- `configs/sweeps/enrollment_prompts.yaml`
- `artifacts/enrollment_prompt_eval/README.md`
- `artifacts/enrollment_prompt_eval/synthetic_prompt_samples.jsonl`
- `tests/inference_pipeline/test_enrollment_prompt_eval.py`
- `tests/run_all_tests.py`
- `tests/run_smoke_tests.py`

## Prompt Strategies

- `short_phrase` (short_phrase): Short phrase; prompt_ids=short_phrase_v1; target=2.0s
- `balanced_sentence` (balanced_phoneme_sentence): Balanced phoneme sentence; prompt_ids=balanced_sentence_v1; target=6.0s
- `multiple_short_phrases` (multiple_short_phrases): Multiple short phrases; prompt_ids=multi_phrase_v1_a, multi_phrase_v1_b, multi_phrase_v1_c; target=10.0s
- `long_paragraph` (long_paragraph): 20-30 second paragraph; prompt_ids=long_paragraph_v1; target=25.0s

## Experiment Inputs And Assumptions

- Prompt sets loaded from /Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/app/inference_pipeline/enrollment/prompt_sets.yaml
- Samples loaded from /Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/artifacts/enrollment_prompt_eval/synthetic_prompt_samples.jsonl
- Synthetic fixtures validate experiment behavior but not product speaker quality.

## Runner Contract Preservation

Enrollment prompt evaluation reads prompt/sample artifacts and embeddings only. It does not modify app/model_runner/external_stub.py, record['inference_audio_path'], predictions/utterances.jsonl, or scoring identity fields.

## Commands

- `.venv/bin/python -m pytest "Software Validation from Datasets/Evaluation Tool/tests/inference_pipeline/test_enrollment_prompt_eval.py"`
- `../../.venv/bin/python -m compileall app/inference_pipeline/experiments scripts/run_enrollment_prompt_eval.py`
- `python scripts/run_enrollment_prompt_eval.py --prompt-sets app/inference_pipeline/enrollment/prompt_sets.yaml --samples-jsonl artifacts/enrollment_prompt_eval/synthetic_prompt_samples.jsonl --sweep-config configs/sweeps/enrollment_prompts.yaml --report reports/component_reports/enrollment_prompts/prompt_comparison_m12_enrollment_prompts.md --run-id m12_enrollment_prompts`
- `../../.venv/bin/python tests/run_smoke_tests.py --only m12-enrollment-prompt-eval-direct`
- `../../.venv/bin/python tests/run_smoke_tests.py --list`
- `../../.venv/bin/python tests/run_all_tests.py --python ../../.venv/bin/python`

## Recommendation

- Recommended prompt set: `multiple_short_phrases`
- Recommended prompt title: `Multiple short phrases`
- Recommended minimum enrollment duration: `8.0000s`

## Metrics By Prompt Set

| rank | prompt set | known accuracy | false-known rate | EER | margin mean | stability mean | per-speaker duration sec | threshold |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | multiple_short_phrases | 1.0000 | 0.0000 | 0.0000 | 0.6937 | 0.9999 | 8.0000 | 0.7000 |
| 2 | balanced_sentence | 1.0000 | 0.0000 | 0.0000 | 0.7030 | 0.9999 | 12.0000 | 0.7000 |
| 3 | long_paragraph | 1.0000 | 0.0000 | 0.0000 | 0.7030 | 1.0000 | 48.0000 | 0.7000 |
| 4 | short_phrase | 1.0000 | 0.0000 | 0.0625 | 0.1666 | 0.9996 | 4.0000 | 0.7000 |

## Cross-Prompt Generalization

- `multiple_short_phrases`: known_accuracy=`1.0000`, cross_prompt_tests=`14`, natural_speech_tests=`3`
- `balanced_sentence`: known_accuracy=`1.0000`, cross_prompt_tests=`14`, natural_speech_tests=`3`
- `long_paragraph`: known_accuracy=`1.0000`, cross_prompt_tests=`14`, natural_speech_tests=`3`
- `short_phrase`: known_accuracy=`1.0000`, cross_prompt_tests=`14`, natural_speech_tests=`3`

## Stability Across Repeated Recordings

- `multiple_short_phrases`: stability_mean=`0.9999`, stability_min=`0.9999`
- `balanced_sentence`: stability_mean=`0.9999`, stability_min=`0.9999`
- `long_paragraph`: stability_mean=`1.0000`, stability_min=`1.0000`
- `short_phrase`: stability_mean=`0.9996`, stability_min=`0.9996`

## EER And TAR@FAR

- `multiple_short_phrases`: EER=`0.0000`, TAR@FAR=FAR 0.01: 1.0000, FAR 0.05: 1.0000, FAR 0.10: 1.0000
- `balanced_sentence`: EER=`0.0000`, TAR@FAR=FAR 0.01: 1.0000, FAR 0.05: 1.0000, FAR 0.10: 1.0000
- `long_paragraph`: EER=`0.0000`, TAR@FAR=FAR 0.01: 1.0000, FAR 0.05: 1.0000, FAR 0.10: 1.0000
- `short_phrase`: EER=`0.0625`, TAR@FAR=FAR 0.01: n/a, FAR 0.05: n/a, FAR 0.10: n/a

## False Known-Speaker Rate By Prompt Set

- `multiple_short_phrases`: `0.0000`
- `balanced_sentence`: `0.0000`
- `long_paragraph`: `0.0000`
- `short_phrase`: `0.0000`

## Duration Vs Performance

- `multiple_short_phrases`: per-speaker duration=`8.0000s`, known_accuracy=`1.0000`, false_known_rate=`0.0000`
- `balanced_sentence`: per-speaker duration=`12.0000s`, known_accuracy=`1.0000`, false_known_rate=`0.0000`
- `long_paragraph`: per-speaker duration=`48.0000s`, known_accuracy=`1.0000`, false_known_rate=`0.0000`
- `short_phrase`: per-speaker duration=`4.0000s`, known_accuracy=`1.0000`, false_known_rate=`0.0000`

## Blockers

- None known.

## Incomplete

- Synthetic samples validate experiment plumbing only; real participant recordings are still required for product-quality prompt selection.
