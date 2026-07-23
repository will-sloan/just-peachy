# Prompt 13 — add alternative backend branch and benchmark hooks

You are working in the existing Evaluation Tool repository.

## Goal
Make the architecture capable of comparing desktop and edge ASR backends without rewriting orchestration.

## Implement
- finish `SherpaMoonshineBackend`
- add any config hooks needed for a Parakeet-style backend if practical
- keep the same `AsrEngine` interface

## Add docs
Create:
- `docs/backend_benchmark_plan.md`

It should define:
- which datasets to benchmark first
- what metrics to compare
- how to decide the desktop default
- how to decide the Raspberry Pi fallback

## Constraints
- do not change the pipeline contract
- do not duplicate orchestration logic
- keep backends swappable by config only

## Acceptance criteria
- at least two ASR backends can be selected by config
- benchmark plan doc exists
- existing pipeline tests still pass
