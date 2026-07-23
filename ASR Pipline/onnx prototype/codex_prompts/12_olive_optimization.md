# Prompt 12 — add Olive optimization workflow after baseline correctness

You are working in the existing Evaluation Tool repository.

## Goal
Add a documented Olive optimization path for the chosen ONNX models without destabilizing the baseline code path.

## Create
- `docs/olive_workflow.md`
- an `olive/` folder with template configs or placeholders for:
  - ASR model optimization
  - optional speaker model optimization

## Workflow requirements
Document:
- baseline benchmark first
- quantization second
- compare accuracy drop vs latency / size gain
- when ORT format is worth using
- when not to optimize further

## If you add code
It should be helper scripts only, for example:
- validating model paths
- invoking Olive CLI with config files
- recording before/after benchmark artifacts

## Constraints
- do not replace the baseline model artifacts automatically
- do not change runtime code to require optimized models
- keep optimized artifacts opt-in

## Acceptance criteria
- Olive workflow is documented
- optimized artifacts can coexist with baseline artifacts
- no existing test path is broken
