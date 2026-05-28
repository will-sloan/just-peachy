# M12 Enrollment Prompt Testing Framework Report

## Milestone

M12 - Enrollment Prompt Testing Framework

## Summary

M12 adds a repeatable enrollment prompt comparison experiment. It loads prompt
strategy definitions, reads per-sample embedding metadata, enrolls speakers on
one prompt set, tests cross-prompt and natural-speech generalization, ranks
prompt sets, and writes a recommendation report.

The implementation is independent of the Evaluation Tool runner. No changes
were made to `app/model_runner/external_stub.py`, dataset selection, scoring,
plotting, report generation, GUI, or the required `predictions/utterances.jsonl`
schema.

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
- `reports/component_reports/enrollment_prompts/prompt_comparison_m12_enrollment_prompts.md`
- `reports/milestones/M12_enrollment_prompt_eval_report.md`

## Behavior Added

- Candidate prompt sets for short phrase, balanced sentence, multiple phrases,
  and 20-30 second paragraph.
- Metadata schema for prompt evaluation samples with speaker id, prompt id,
  prompt set id, recording condition, embedding model, duration, sample id, and
  embedding source.
- Cross-prompt experiment that enrolls on prompt set A and tests on prompt set B
  plus synthetic natural speech.
- Prompt ranking by false-known rate, known accuracy, EER, score margin,
  stability, and enrollment duration.
- Prompt comparison script and synthetic repeatable artifact inputs.
- M12 entries in the all-test and smoke-test harnesses.

## Runner Contract Preservation

Enrollment prompt evaluation reads prompt/sample artifacts and embeddings only.
It does not change:

- `record["inference_audio_path"]`
- `recording_id`
- `utt_id`
- `start_sec`
- `end_sec`
- `predictions/utterances.jsonl`

## Validation Commands

Run from `/Users/billy/Documents/just-peachy`:

```bash
.venv/bin/python -m pytest "Software Validation from Datasets/Evaluation Tool/tests/inference_pipeline/test_enrollment_prompt_eval.py"
```

Run from `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool`:

```bash
../../.venv/bin/python -m compileall app/inference_pipeline/experiments scripts/run_enrollment_prompt_eval.py
../../.venv/bin/python scripts/run_enrollment_prompt_eval.py --run-id m12_enrollment_prompts --report "reports/component_reports/enrollment_prompts/prompt_comparison_m12_enrollment_prompts.md"
../../.venv/bin/python tests/run_smoke_tests.py --only m12-enrollment-prompt-eval-direct
../../.venv/bin/python tests/run_smoke_tests.py --list
../../.venv/bin/python tests/run_all_tests.py --python ../../.venv/bin/python
```

## Results

- Focused M12 tests: `4 passed`
- Compile check: passed
- Script smoke: passed; recommended `multiple_short_phrases`
- Required component report generated:
  `reports/component_reports/enrollment_prompts/prompt_comparison_m12_enrollment_prompts.md`
- M12 smoke harness check: passed
- Smoke harness listing: passed and includes `m12-enrollment-prompt-eval-direct`
- All-test harness: passed, including `tests/inference_pipeline/test_enrollment_prompt_eval.py` labeled `M12`

## Known Limitations

- The tracked sample set is synthetic and validates experiment plumbing only.
- Real participant recordings and real embedding model outputs are still
  required before treating the prompt recommendation as product-quality.
- The experiment is not wired into the end-to-end external runner, by design.

## Blockers

- None known for the scoped M12 framework implementation.
