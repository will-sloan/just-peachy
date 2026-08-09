# Phase 4 Report: Persistent Campaign Executor and State

## Objective and result

Stage 4 is complete. The Evaluation Tool now has an additive persistent campaign executor that plans deterministic subsets of frozen Stage 2 scenarios, stores transactional campaign/scenario state, leases work to one worker at a time, supervises each scenario in a subprocess, handles heartbeats/timeouts/stops/interruption, classifies failures, preserves partial results, resumes after restart, and accepts success only after Stage 3 artifact validation.

The implementation reuses the Stage 1 `ConfiguredEvaluatorRunner`, Stage 2 manifests/scenario identities, and Stage 3 layout/atomic writers/checksums/completion validator. Existing evaluator, augmentation, inference, scoring, plotting, reporting, simulation, external runner, GUI, and ordinary CLI behavior were not replaced.

No model download, GPU execution, resource telemetry collection, distributed coordinator, result merger, or parallel GPU execution was added or run.

## Implemented files

- `app/campaign_executor/state.py`: `campaign-database.v1`, explicit states/transitions, attempts, atomic leases, heartbeats, stale-lease recovery, stop requests, retry queueing, event persistence, and status summaries.
- `app/campaign_executor/planner.py`: catalog validation, deterministic filtering/ordering, campaign ID derivation, immutable manifest publication, exact benchmark copy/checksum validation, scenario directory initialization, and database registration.
- `app/campaign_executor/executor.py`: disk checks, one-process-at-a-time supervision, timeout/stop/Ctrl+C handling, heartbeats, retry/OOM classification, partial-result archives, completion recovery, skip-completed validation, and terminal progress.
- `app/campaign_executor/runtime.py`: one frozen ASR scenario through the existing configured runner, runtime augmentation, scorer, plotter, reporter, and Stage 3 artifact adapter.
- `app/campaign_executor/synthetic_worker.py`: deterministic process behavior for executor qualification only.
- `app/campaign_executor/cli.py`: `campaign plan`, `validate`, `list`, `run`, `resume`, `status`, `stop`, `retry`, and `validate-artifacts`.
- `app/campaign_executor/README.md`: purpose, inputs, outputs, states, retry rules, Anaconda Prompt, Command Prompt, PowerShell, and test commands.
- `tests/automated_evaluation/test_stage4_campaign_executor.py`: model/GPU-free persistent-process qualification.

Updated files:

- `app/cli/main.py` registers the additive `campaign` command group;
- `README.md` documents Stage 4 operation;
- `docs/automated_evaluation/README.md` records the Stage 4 boundary and commands;
- `docs/automated_evaluation/protected_interfaces.md` records the versioned database/state contracts;
- this report.

## Persistent state model

The existing Stage 3 `database/campaign.sqlite` reservation is now implemented as `campaign-database.v1`. SQLite uses WAL mode, full synchronous commits, foreign keys, a 30-second busy timeout, and `BEGIN IMMEDIATE` for all state-changing operations.

The database stores:

- immutable campaign manifest hash;
- global scenario ID and full hash;
- deterministic ordinal;
- detailed state;
- worker ID and hostname;
- attempt and configured maximum-attempt counts;
- first start, attempt end, heartbeat, and update timestamps;
- lease owner and expiry;
- child process ID and exit code;
- exception category and concise sanitized error;
- expected Stage 3 artifacts;
- completion-validator result;
- retry eligibility;
- campaign/scenario stop requests;
- per-attempt history;
- machine-readable events.

Detailed execution state remains in SQLite. The released Stage 3 `scenario-status.v1` is not changed: it remains the broad artifact-completion/count summary. This avoids a breaking schema change.

## States and transitions

Implemented states are:

- `pending`;
- `assigned`;
- `running`;
- `succeeded`;
- `succeeded_with_warnings`;
- `failed_retryable`;
- `failed_terminal`;
- `timeout`;
- `out_of_memory`;
- `interrupted`;
- `stopped`;
- `invalid`.

Transitions are checked inside the same database transaction that updates the lease/attempt. A worker can heartbeat or finalize only while its exact lease owner, scenario hash, and attempt number still match. Competing claim attempts cannot both acquire the same scenario.

## Planning and identity protection

`campaign plan` validates every source scenario with `scenario-definition.v1`, sorts by global scenario ID, and supports exact IDs, inclusive ID ranges, panel/tier filters, and exact `family=name` component filters. Dry-run prints the deterministic plan and creates nothing.

The campaign ID may be operator-supplied or derived from the source catalog SHA-256 and selected global scenario IDs. Referenced benchmark Parquet files are copied, schema-validated, and SHA-256 checked; source audio is never copied.

Each queued scenario retains its original global ID and full hash. The database refuses to bind an existing ID to another hash or registration. Before execution, the resolved scenario is revalidated. The runtime resolver compares current pipeline/config/component/model identities to the identities frozen into the scenario. A changed result-affecting parameter with an old ID is rejected.

## Execution and completion behavior

The default executor runs one scenario subprocess at a time. It uses the existing configured evaluator flow:

```text
frozen manifest slice
-> existing runtime augmentation
-> existing ConfiguredEvaluatorRunner / PipelineRunner
-> existing standardized predictions
-> existing scorer
-> existing plots and report
-> Stage 3 typed artifact adapter
-> checksum reconciliation and completion validation
```

The ordinary evaluator runs in an attempt-specific audit workspace so its existing extra files cannot violate the strict Stage 3 exchange directory. Only registered Stage 3 artifacts are atomically published into the scenario directory.

A child exit code of zero is only a candidate success. The parent mirrors a completion event, revalidates every materialized artifact, rebuilds `checksums.json`, and calls `validate_scenario_completion()`. Only `complete` can transition to `succeeded` or `succeeded_with_warnings`. Incomplete, corrupt, or incompatible success output becomes `invalid`.

Before claiming queued work, the executor validates existing scenario artifacts. Complete output is recovered/marked successful and skipped. A database success whose output is later corrupt becomes `invalid`; its files are not overwritten.

## Failure, timeout, stop, and resume rules

- Deterministic schema/configuration/reference/hash failures are terminal.
- Recognized transient process/I/O failures retry only while the hashed policy permits another attempt.
- OOM retries require an explicit `failure_policy.oom_retry.enabled=true` and an approved unchanged safe restart action in the scenario.
- Timeout terminates the child, preserves artifacts, and records `timeout`.
- Scenario stop requests are polled during execution and terminate only that child.
- A campaign stop prevents new leases and stops an active child at its next poll.
- Ctrl+C/requested interruption terminates the child and records resumable `interrupted` state.
- Expired `assigned`/`running` leases become resumable `interrupted` state after restart.
- Interrupted attempts remain resumable independently of the ordinary failure retry budget.
- Before a retry, prior predictions/metrics/resource logs/reports/status/checksums move to `audit/partial_results/<scenario_id>/attempt_<number>`.
- One scenario failure does not halt unrelated scenarios.

## CLI

The additive command group is:

```text
campaign plan
campaign validate
campaign list
campaign run
campaign resume
campaign status
campaign stop
campaign retry
campaign validate-artifacts
```

Existing top-level `run`, `full`, `score`, `report`, `gui`, and `list-datasets` commands are unchanged. Full commands and examples are in `app/campaign_executor/README.md`.

## Verification evidence

Focused Stage 4 process/state suite:

```bat
python -m pytest tests\automated_evaluation\test_stage4_campaign_executor.py -q --basetemp artifacts\stage4_pytest_focus_final
```

Result: `22 passed`.

Protected automated-evaluation/inference/model-runner regression selection:

```bat
python -m pytest tests\automated_evaluation tests\inference_pipeline tests\model_runner -q --basetemp artifacts\stage4_pytest_regression
```

Result: `433 passed, 2 warnings`. The warnings are existing Silero/importlib-resources and TorchScript deprecations.

Static and GUI validation:

```bat
python -m ruff check --no-cache app\campaign_executor app\cli\main.py tests\automated_evaluation\test_stage4_campaign_executor.py
python -m app.gui.validation_harness
python -m compileall -q app\campaign_executor app\cli\main.py
```

Results: Ruff passed, GUI validation passed, and bytecode compilation passed.

The real Stage 2 catalog was also dry-run planned for `scenario_01aa02f9a7d4`. It produced the stable campaign plan `campaign_e29b22b81beb`, selected the exact `manifest_0bd28359f11a`, and wrote nothing. Separately, the runtime adapter resolved that scenario's current `live_mic_whisper_base` identity and selected its exact 60 LibriSpeech manifest rows with all audio present. Those checks did not load a model or run inference.

## Acceptance criteria

| Criterion | Result |
|---|---|
| Interrupted campaigns resume | Pass: live synthetic child interruption and fresh-executor resume test. |
| Validated successes skip | Pass: checksum preserved and attempt count unchanged on rerun. |
| Corrupt successes do not skip | Pass: prior success is invalidated and never overwritten. |
| Unrelated scenarios survive failures | Pass: terminal failure followed by independent success. |
| State transitions are atomic and valid | Pass: transactional transition/forged-owner/competing-lease tests. |
| Changed result-affecting parameters cannot reuse IDs | Pass: scenario/hash validation and database rebinding rejection. |
| Completed work cannot be overwritten silently | Pass: immutable planner checks plus validated skip/invalidation behavior. |
| Timeout, stop, OOM, disk, retry limits, and stale leases work | Pass: supervised synthetic subprocess tests. |
| Partial results survive retry | Pass: prior attempt artifacts archived and verified. |
| Existing Evaluation Tool behavior remains functional | Pass: 433 protected tests and GUI validation. |

## Limits and deferred work

- Stage 4 intentionally runs one scenario subprocess at a time per machine.
- Resource CPU/RAM/GPU/VRAM/temperature/power telemetry remains a later stage.
- Shared/network campaign coordination and cross-machine merge validation remain unimplemented. Two users should use pre-agreed non-overlapping IDs/ranges/config selections.
- The runtime adapter currently materializes complete Stage 3 output for ASR scenarios. VAD-only, embedding, verification, and diarization execution remain blocked until their real output adapters are implemented; the executor marks unsupported scenario types as deterministic configuration failures rather than fabricating artifacts.
- Automatic operating-system startup after reboot is not installed. Restart safety is provided by persistent SQLite state, lease expiry, `campaign resume`, and artifact validation.
- Real model/GPU execution was deliberately not run in Stage 4 verification. The separately pinned CUDA qualification remains the next gate before standard/large benchmarks or performance selection.
- Campaign result merging, comparative plots, analysis manifests, and final campaign reports remain later stages.
