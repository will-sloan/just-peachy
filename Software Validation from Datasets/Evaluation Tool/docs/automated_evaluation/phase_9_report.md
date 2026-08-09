# Phase 9 — Extended Backend Integration and Scientific Screening

## Outcome

Stage 9 integration is implemented. The nine real Stage 8-qualified backends are selectable through the ordinary component catalog, pipeline resolver, immutable scenario contract, campaign executor, and staged analysis framework. Four blocked backends are excluded with exact reasons. Sherpa-ONNX diarization is integrated only for composition; its scientific evaluation remains Stage 11.

The released small-tier plan contains 19 one-family candidates and 228 globally identified scenarios over the same 165 controlled-clean items used by core screening. It is split into four non-overlapping environment catalogs: 96 `core-cpu`, 60 `extended-local`, 60 `onnx`, and 12 `wespeaker` scenarios. A fresh real one-item smoke reran all nine eligible backends and passed 9/9.

## Contracts and implementation

- The component registry now records qualified extended status, Stage 8 backend identity, compatible environment profiles, supported parameters, and observed model tree identities.
- The resolver accepts or infers one environment profile and rejects active components with no common profile.
- Pipeline/scenario identity preserves the selected profile and Stage 8 environment/package/model evidence.
- The campaign runtime reconstructs and verifies that frozen environment profile alongside component and model identity.
- The qualification registry is checksummed against the exact Stage 8 summary and cannot silently admit an unavailable backend.
- The Stage 9 protocol fixes benchmark items, conditions, controls, scope boundaries, and declared Pareto objectives.
- Analysis separates global model-quality frontiers from runtime frontiers grouped by environment and hardware. It never uses an opaque aggregate score.

## Required outputs

`benchmarks/stage9/` contains the global and per-environment scenario catalogs, component comparison table, advancement/exclusion report, environment compatibility matrix, benchmark coverage report, and shortlist manifest. `runs/extended_screening/` contains fresh real smoke evidence and smoke-scoped versions of those handoffs. Full campaign analysis will produce the same handoffs under `automated_runs/<campaign_id>/analysis/extended_screening/`.

## Validation

- Stage 9 contract/integration tests: 17 passed.
- Real Stage 9 rerun: 9/9 eligible backends passed on one identical utterance.
- Catalog coverage: all nine eligible backend IDs appear in normal scenarios.
- Environment conflict tests reject incorrect and mixed profile resolutions.
- Missing ASR and embedding outputs remain in expected denominators.
- Ruff passes for the Stage 9 package and modified integration paths.
- Affected core regressions passed: Stage 0 (9), Stage 1 non-real (19), Stage 2 (35), Stage 4 (22), Stage 7 non-real (12), Stage 8 (13 plus one expected skip), inference registry/adapters (18), and model runners (5).

## Scientific execution boundary

The one-item smoke is not represented as the completed 165-item scientific screen and does not advance a shortlist. The 228-scenario campaign is materialized and ready for unattended execution with the matching environment interpreter, telemetry, resume, worker assignment, transfer, merge, and analysis contracts. Full data collection is a long-running campaign operation; advancement remains `pending_scientific_results` until those validated results are analyzed.

Stage 9 does not perform Stage 10 speaker recognition, Stage 11 diarization science, GPU concurrency qualification, or a full component Cartesian product.
