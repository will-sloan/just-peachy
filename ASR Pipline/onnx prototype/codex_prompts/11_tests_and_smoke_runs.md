# Prompt 11 — add tests and smoke-run instructions

You are working in the existing Evaluation Tool repository.

## Goal
Make the new ONNX pipeline patch testable and safe to iterate.

## Add / update tests
Cover:
- contracts
- config loading
- adapter round-trip
- audio crop / resample
- matching thresholds
- pipeline behavior with dummy components
- failure behavior when model paths are missing

## Add docs
Create:
- `docs/onnx_pipeline_smoke_tests.md`

Include:
1. exact command to run a tiny dummy test
2. exact command to run a tiny real ASR test on `cmu_arctic`
3. what files to inspect in the run folder
4. what indicates success
5. what common failures mean

## Constraints
- do not add giant benchmark suites yet
- focus on fast smoke tests
- keep commands copy-pasteable

## Acceptance criteria
- tests pass
- smoke-test doc exists
- first-time integrator can follow the steps without guessing
