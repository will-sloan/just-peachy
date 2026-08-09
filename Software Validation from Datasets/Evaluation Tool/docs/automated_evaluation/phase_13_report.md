# Phase 13 Final Acceptance and Documentation Report

## Outcome

**Final verdict: `release_ready_with_documented_limitations`.**

The accepted release boundary covers protected Evaluation Tool behavior, deterministic benchmark/scenario contracts, configured pipeline execution, persistent campaigns, atomic/checksummed artifacts, resume, telemetry contracts, independent worker assignment/merge, component qualification paths, speaker/diarization protocol contracts, and synthetic release-analysis mechanics.

It does not claim that a scientifically best pipeline has been selected. No real small, standard, or large release campaign is complete.

## Requirements summary

| Status | Count | Requirement IDs |
|---|---:|---|
| Passed | 17 | A01–A06, A08–A12, A14, A22, A24–A27 |
| Limited | 10 | A07, A13, A15–A21, A23 |
| Failed | 0 | None after correction/re-validation |
| Not applicable | 0 | N/A is applied at individual metric/output eligibility, not to the framework-level matrix |

The complete expected behavior, implementation, test, artifact, and disposition evidence is in [Final acceptance audit](final_acceptance_audit.md).

## Corrections made

### Windows atomic publication

Audit finding F-01 exposed a transient WinError 32 when replacing a completed Parquet artifact during a heavily combined test. The correction:

- retries only recognized Windows access/sharing violations 5, 32, and 33;
- uses a bounded 1.575-second backoff window;
- preserves immediate failure for permanent or non-Windows errors;
- prevents temporary-file cleanup from masking the primary error;
- leaves schemas, checksums, target names, overwrite protection, and completion semantics unchanged;
- adds a deterministic injected-lock regression test.

Changed files:

- `app/artifact_contracts/atomic.py`
- `tests/automated_evaluation/test_stage3_artifact_contracts.py`

### Documentation and current command/profile naming

- Created `final_acceptance_audit.md`, `system_guide.md`, `quick_reference.md`, `current_evaluation_tool_architecture.md`, and this report.
- Added discoverable links to the Evaluation Tool and automated-evaluation READMEs.
- Marked three superseded root planning/architecture documents as historical.
- Updated current worker examples from the Stage 0 historical profile label `core_cpu_development` to the active Stage 8 profile `core-cpu`. Historical machine-readable contracts/tests were not rewritten.

## Tests re-run

| Validation | Result |
|---|---|
| Focused injected WinError/interruption/previous failing duplicate | 3 passed |
| Affected Stage 3/4/5/6/12 set | 85 passed, 1 expected skip |
| Complete automated-evaluation suite | 228 passed, 2 expected skips, 2 third-party deprecation warnings in 362.03 s |
| Protected inference/model/path/install regressions | 331 passed, 2 third-party deprecation warnings in 23.01 s |
| GUI validation harness | Passed |
| Ruff check and format | Passed for both changed Python files |

The expected full-suite skips are the real CUDA-event telemetry smoke in the CPU interpreter and WebRTC qualification in the core interpreter. Their dedicated environments/statuses remain explicit.

## Artifacts inspected

- Stage 1 real Whisper Tiny and Base ordinary Evaluation Tool runs.
- Fresh Phase 13 real Whisper Base one-item run: `runs/20260808_094235_cmu_arctic_full_base_one_item` (41 files, 362,349 bytes, one prediction, no failed/missing item, WER 0.25).
- Stage 2 small/standard/large authoritative manifests, manifest summaries, RIR audit, scenario catalog, and golden hashes.
- Stage 5 typed telemetry samples, availability reasons, spans, and summary.
- Stage 7/8/9 core and extended qualification/smoke registries and outputs.
- Stage 10 three-tier speaker manifests and four clean ECAPA contract-smoke results, including literal `Unknown`.
- Stage 11 three-tier native manifests and one valid Sherpa RTTM/UEM/scoring contract smoke.
- Stage 12 persistent synthetic qualification evidence.
- Fresh full-suite two-worker synthetic split/run/transfer/merge/result-index/analysis artifacts before temporary test sandboxes were removed.

All eight explicitly named Phase 13 pytest temporary directories were removed after inspection. The retained real guide run is small and serves as reproducible documentation evidence.

## Documentation created

- [Final acceptance audit](final_acceptance_audit.md)
- [Owner/operator system guide](system_guide.md)
- [Quick reference](quick_reference.md)
- [Current architecture](current_evaluation_tool_architecture.md)
- This Phase 13 report

The system guide covers installation and eight environment profiles, all active component families and backend dispositions, exact pipeline order, datasets/panels/conditions, campaign lifecycle, interruption/resume, two-machine work, artifacts, a synthetic end-to-end trace plus a real evaluator trace, metrics, all 20 registered plots, comparison/statistical rules, troubleshooting, states/failures, reproducibility, backend extension, glossary, and limitations.

## Commands verified

A parser-level audit extracted 81 documented `run_evaluation.py` lines from the system guide and quick reference. All mapped to valid options across 28 distinct current command paths:

- ordinary `run` and `full`;
- `screening qualify`;
- `extended-screening smoke`;
- `speaker-protocol smoke`;
- `diarization smoke`;
- campaign plan, validate, list, run, status, stop, resume, retry, artifact validation, assignment, assignment validation/run, worker-copy preparation, export, transfer validation, merge, and merged validation;
- analysis index, validate, coverage, run, and release status.

No unknown command or option was found. Installation/profile scripts and seven referenced script/config/catalog paths exist. Twenty-nine local documentation links resolve.

Execution-level examples validated:

- exact small controlled-clean Whisper Base campaign dry run: 12 scenarios, no write;
- runtime component listing: 27 executable catalog entries;
- exact one-item configured Whisper Base command: successful inference/scoring/plots/report;
- synthetic two-worker campaign execution and analysis: successful full contract trace.

Commands that intentionally create, stop, transfer, or merge an operator's named campaign were parser-verified and are covered by subprocess/end-to-end tests; they were not executed against a user campaign during documentation validation.

## Consistency checks

- Component catalog: 27 runtime entries.
- Environment profiles: 8 active Stage 8 profiles.
- Campaign metric registry: 19 headline metrics.
- Plot registry: 20 eligibility-gated plots.
- Executor state model: 12 documented states.
- Quick-start identity: `scenario_8cff9abad3fc` is current v1 small, controlled-clean, CMU Arctic, clean, 90-row, Whisper Base CPU.
- Local links checked: 29, all valid.
- Documented paths checked: 7, all present.
- Secret/private-identity scan: no credential values or private name mapping found in shared qualification artifacts.
- Audit/guide verdict and limitations: consistent.

## Unresolved risks and known limitations

- Bedroom RIR selection remains unresolved; only exact Dining room and Restaurant RIRs are executable in current campaign scope.
- Stage 5 real CUDA-event telemetry timing is not qualified in `core-cuda`.
- Dual GPU-job concurrency is not qualified; one GPU-heavy scenario remains the default.
- No small/standard/large scientific release campaign or performance winner exists.
- Stage 10 and Stage 11 real evidence is bounded contract smoke evidence.
- The campaign metric registry does not expose every detailed stage metric as a headline metric.
- Dedicated resource timelines, latency ECDFs, failure funnels, diarization timelines, and subgroup forest plots are not implemented.
- Analysis lacks arbitrary metric/plot/filter/table-only CLI selectors.
- Scientific comparison eligibility still depends on paired manifests, reference compatibility, repeated finalists, and authorized metadata.

## Unqualified backends

- WeNet: required `final.zip` absent.
- pyannote Community-1: personal terms/token and local qualification required.
- Picovoice Falcon: access key/license and local qualification required.
- NeMo: Linux/CUDA platform, configuration, and active checkpoints required.
- WebRTC VAD and WeSpeaker remain qualified with warnings rather than unconditionally qualified.

## Final documentation readiness

Documentation is ready for an owner/operator who knows basic Python and PowerShell/Anaconda Prompt but does not know the repository architecture. Commands, paths, component/profile counts, scenario identity, metrics, plots, states, evidence labels, and limitations were checked against current implementation and artifacts.

The system guide does not override the audit: the release remains **`release_ready_with_documented_limitations`**.
