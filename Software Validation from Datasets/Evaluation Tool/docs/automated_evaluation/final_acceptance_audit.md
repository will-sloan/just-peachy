# Final Acceptance Audit

> Historical Stage 13 audit retained for traceability. Its commit and verdict
> describe the 2026-08-08 checkpoint, not the current production handoff. Use
> `operational_launch_readiness.md` and `launch_control_sheet.md` for current
> CPU/CUDA status and launch decisions.

## Document control

| Field | Value |
|---|---|
| Audit scope | Automated Speech Evaluation framework, Stages 0–12, and protected Evaluation Tool behavior |
| Repository commit inspected | `e7e5516991b95f4e7c915e852fc0b4f5bae7cd11` |
| Audit date | 2026-08-08 |
| Host | Windows, NVIDIA GeForce RTX 3080 10 GB |
| Core interpreter | repository `.venv`, Python 3.12.7, PyTorch 2.11.0 CPU |
| CUDA interpreter | `core-cuda`, Python 3.12.7, PyTorch 2.11.0+cu128, CUDA 12.8 |
| Preliminary verdict | **`not_release_ready`** |
| Final verdict | **`release_ready_with_documented_limitations`** |

This is the independent acceptance record required before the owner/operator guide is written. The preliminary verdict was intentionally conservative because audit finding F-01 was still open at that point in the ordered audit. F-01 has since received the narrow correction and re-validation recorded below. Scientific benchmark completion, unavailable licensed backends, and unresolved Bedroom RIR selection remain documented limitations; they do not invalidate the qualified framework mechanics.

## Audit method and evidence boundary

The audit began read-only. It inspected repository state, source and configuration contracts, Stage 0–12 reports, registries, schemas, command help, environment profiles, representative real outputs, representative synthetic campaign outputs, and tests. No source was changed before this preliminary audit was recorded.

Claims in this document use four evidence classes:

- **Implementation:** current source, YAML, JSON schema, or registry behavior.
- **Test:** a test executed during this audit or a reproducible phase result.
- **Artifact:** a schema-valid output produced by a real or synthetic run.
- **Limitation:** functionality that is absent, blocked, unqualified, or not yet exercised at scientific scale.

Historical planning documents are not treated as proof. Stage reports are supporting evidence, but fresh tests and current artifacts take priority when they disagree.

## Executive assessment

The repository contains an integrated, versioned framework rather than a separate speech-pipeline repository. The framework can resolve configured pipelines, use the existing normalized dataset and augmentation paths, execute ordinary Evaluation Tool scoring/reporting, build deterministic manifests and scenario identities, publish typed/checksummed artifacts, persist and resume campaigns, collect resource telemetry, divide work between independent machines, merge copied results, qualify components, run speaker and diarization protocols, and construct a validated analysis manifest and report bundle.

Protected Evaluation Tool behavior passed fresh regression and GUI validation. Real one-item or bounded qualification evidence exists for the core Whisper, VAD, embedding, several extended, speaker, and Sherpa diarization paths. The framework does **not** yet contain a completed small, standard, or large scientific release campaign, and it must not be used to claim a best production pipeline from the smoke evidence.

One combined test exposed a transient Windows sharing violation during atomic Parquet publication. The same test passed in isolation, confirming that the failure is load/timing sensitive rather than deterministic. Since one-week unattended operation is an approved requirement, this is a release blocker until a narrow bounded retry is implemented and re-validated.

## Requirements matrix

Status meanings: **Pass** means current implementation, test, and appropriate artifact evidence agree. **Limited** means the implemented contract works within a narrower qualified boundary. **Fail** means an approved requirement is currently broken. **N/A** means the metric or output cannot validly be produced for the available reference/output pair.

| ID | Expected behavior | Implementation evidence | Test evidence | Artifact evidence | Status |
|---|---|---|---|---|---|
| A01 | Audit begins read-only and distinguishes facts from plans | Git status/diff, current registries, schemas, CLI, and reports inspected before edits | No modifying command run before this document | Existing Stage 1–12 outputs inspected in place | Pass |
| A02 | Existing GUI, CLI, simulation, scoring, plotting, reporting, dataset and augmentation behavior remains usable | Protected entry points and existing runners remain present; configured runner is additive | 331 protected tests passed; GUI validation passed | Stage 1 Tiny/Base ordinary runs contain predictions, metrics, plots, and reports | Pass |
| A03 | Active components have explicit identity, dependencies, assets, contracts, device settings, and qualification disposition | Stage 0 component/model registries plus Stage 8 qualification overlay; 37 component records | Catalog, resolver, qualification, and smoke suites passed | Stage 7–11 qualification summaries inspected | Pass |
| A04 | Environments are reproducible and capability-specific | Versioned environment profiles and lock/freeze material exist; core CPU/CUDA and extended environments inspected | `pip check` passed in core CPU and core CUDA; environment tests passed | Environment fingerprints and Stage 8 qualification evidence inspected | Pass |
| A05 | Benchmark selection is deterministic, immutable, versioned, and independent of dataframe order | Manifest contract v1, canonical hashing, stable rank seed 3800, Parquet authority | Determinism, golden, portability, and shortfall tests passed | Small 405, standard 2,083, large 8,258 source rows; all validate | Pass |
| A06 | Controlled augmentation is allowed only for approved clean rows; native conditions are protected | Per-row policy and augmentation guard enforce panel/dataset/subset restrictions | Augmentation-blocking tests passed | Manifest policies and scenario conditions inspected | Pass |
| A07 | RIR identities are exact; no silent substitution; current scope is Dining room, Bedroom, Restaurant | RIR registry records requested/resolved path and SHA-256; ParkingLot is never Kitchen | RIR resolution tests passed | Dining and Restaurant approved; Bedroom unresolved; Kitchen unresolved; 270 WAV files observed | Limited |
| A08 | Scenario identities are portable, canonical, versioned, and change for result-affecting fields | Scenario/canonical/hash contracts v1; SHA-256 12-hex IDs; identity exclusions explicit | Golden hash, path separator, null/absent, float, schema, and collision sanity tests passed | Golden `scenario_6f56ca56fd53`; 108-scenario catalog inspected | Pass |
| A09 | Scenario artifact requirements are typed, versioned, conditional, and completeness-validatable | Artifact registry defines 30 artifacts and six scenario profiles | Schema, missing/conditional/count/stale-temp tests passed | Stage 1, 10, 11, and synthetic campaign artifacts validate | Pass |
| A10 | Atomic writes and checksums detect interruption, corruption, and incomplete transfer | Temporary-write/validate/checksum/replace protocol; bounded retry for recognized transient Windows sharing violations; checksum manifests | Injected-lock test passed; affected set 85 passed/1 skipped; full automated suite 228 passed/2 skipped | Corrected publication path completed in full two-worker synthetic workflow | Pass |
| A11 | Persistent executor provides states, leases, heartbeat, timeout, retry, stop, resume, skip-complete, and failure isolation | Stage 4 campaign state/CLI implementation and state transition rules inspected | Interruption, stale lease, competing lease, timeout, stop, retry, OOM, disk, corrupt-success, and resume tests passed | Synthetic campaign status/events inspected | Pass |
| A12 | Resume skips only checksum/schema-valid completed scenarios and preserves partial work | Completion validator is used before skip; attempts retain scenario identity | Resume and partial-preservation tests passed | Synthetic scenario status and checksums reconcile | Pass |
| A13 | CPU/GPU telemetry is nullable with reasons and component spans do not alter predictions | Stage 5 resource sampler, availability registry, summaries, span channel | CPU/fake GPU/missing-NVML/process-tree/gap/peak/span tests passed | 112-sample synthetic telemetry Parquet and summary inspected | Limited |
| A14 | Two-machine assignments are deterministic, non-overlapping, independently executable, and safely mergeable | Assignment/transfer/merge commands and schemas; no network SQLite dependency | Stage 6 split/run/transfer/merge tests and corrected combined suite passed | Four-scenario two-worker merged synthetic index inspected | Pass |
| A15 | Core screening compares fixed items one family at a time without a Cartesian product | Stage 7 targeted screening planner and declared advancement/Pareto rules | Core planning, metric, denominator, and real qualification tests passed | 84 planned scenarios and nine CPU qualification results inspected | Limited |
| A16 | Extended backends expose setup/qualification status and targeted screening | Stage 8 environment/asset registry and Stage 9 planner/analyzer | Nine available backend smokes and qualification tests passed | 228 planned scenarios; nine real one-item smoke results | Limited |
| A17 | Speaker manifests prevent leakage; enrollment is backend-specific; Unknown remains scoreable | Stage 10 immutable protocol and typed embedding/decision artifacts | Leakage, mismatch, threshold, metric, Unknown, and real smoke tests passed | All three tiers validate; four clean ECAPA smokes validate; literal `Unknown` inspected | Limited |
| A18 | Diarization preserves timebase, anonymous-label semantics, segmentation provenance, and emits metrics only when valid | Stage 11 RTTM/UEM contracts and backend availability registry | Parser, alignment, permutation, overlap, collar, UEM, provenance, and smoke tests passed | Sherpa one-item AMI output validates; timebase clipping warning retained | Limited |
| A19 | Metric formulas use correct denominators and preserve failed/missing items | Stage 7/10/11 metric implementations and Stage 12 metric registry | Deterministic metric and denominator tests passed | Detailed stage outputs and 19-metric analysis availability registry inspected | Limited |
| A20 | Statistical comparisons are paired where appropriate and declare eligibility, counts, uncertainty, and multiplicity policy | Stage 12 comparison/statistics implementation and analysis guide | Stage 12 statistical and synthetic release tests passed | Synthetic comparison tables inspected | Limited |
| A21 | Plots are eligibility-gated and skipped plots are explicit rather than misleading | Stage 12 plot registry with 20 registered plots and prerequisite checks | Plot eligibility/status tests passed | Synthetic analysis generated 2 plots and explicitly skipped 18 | Limited |
| A22 | Result index reconciles campaign, scenario, prediction, metric, failure, resource, speaker, and diarization artifacts | Stage 12 index builder and Stage 3/6 validation contracts | Reconciliation, duplicate, missing, transfer, and corruption tests passed | Four-scenario merged synthetic input index inspected | Pass |
| A23 | Analysis manifest can be handed to another analyst without executor knowledge | Versioned analysis manifest, checksums, input index, analysis CLI and guide | Manifest validation and end-to-end synthetic analysis tests passed | Synthetic release bundle contains manifest, tables, plots, reports, and checksums | Limited |
| A24 | Operator documentation is complete, current, discoverable, and command-verified | System guide, quick reference, current architecture, README navigation, historical notices, and Phase 13 report | 81 documented CLI lines/28 command paths and 29 local links verified; real one-item guide command passed | Fresh 41-file Whisper Base run and report inspected | Pass |
| A25 | Shared artifacts avoid credentials, private identity maps, and unnecessary sensitive absolute paths | Credential values excluded; privacy-safe speaker IDs; exchange schemas use portable paths | Secret-pattern and path-portability scans passed | No credential/private-name leakage found in shared qualification artifacts | Pass |
| A26 | Windows path length and cross-machine portability are considered | Short campaign/scenario IDs, project-relative identities, transfer validators | Long-path, Windows/Linux separator, and cross-machine tests passed | Synthetic transfer/merge artifacts inspected | Pass |
| A27 | Representative acceptance suite covers protected behavior and Stages 0–12 | Test collection spans ordinary and automated paths | Corrected automated suite: 228 passed, 2 expected skips; protected: 331 passed; GUI validation passed | Corrected synthetic campaign/merge/analysis artifacts inspected | Pass |

## Component qualification inventory

The Stage 0 registry is the component-definition baseline. Stage 8 qualification evidence is the authoritative status overlay where Stage 0 blocker text is stale. Updating qualification fields inside identity-bearing component records during this audit would risk changing scenario reconstruction and is therefore not an approved narrow correction.

| Family | Qualified or contract-qualified | Qualified with warnings | Unavailable or blocked | Audit interpretation |
|---|---|---|---|---|
| ASR | Whisper Tiny, Base, Small; Faster-Whisper; Sherpa-ONNX; Vosk; no-op contract | None | WeNet model asset absent | Whisper core CPU and CUDA have real repeated evidence. No scientific winner has been selected. Whisper Large is out of scope. |
| VAD | Energy, Silero, Sherpa-ONNX; no-op contract | WebRTC VAD | None | Full-record/no-VAD is a valid baseline. WebRTC warnings must remain visible. |
| Segmentation | VADChunker; no-op/full-record contract | None | None | When diarization supplies turns, those turns control downstream segmentation; an external VAD must not be claimed as final segmentation. |
| Speaker embedding | SpeechBrain ECAPA, Resemblyzer, Sherpa-ONNX; no-op contract | WeSpeaker | None | Stage 10 scientific protocol currently has bounded ECAPA smoke evidence, not a full degraded benchmark. |
| Matching | Cosine matcher contract; no-op contract | Fixed example thresholds are uncalibrated | None | Deployment thresholds must come from backend-specific held-out calibration, not legacy demo YAML. |
| Diarization | Sherpa-ONNX bounded Stage 11 smoke; no-op contract | None | pyannote and Falcon require authorization/credentials; NeMo is platform/asset blocked | Anonymous labels stay anonymous unless a valid enrolled-speaker decision supersedes them. |
| Workflow support | Enrollment workflow | Temporal evidence is contract-only | None | Legacy demo enrollment is not a Stage 10 scientific enrollment result. |

## Confirmed pipeline order

The active implementation order is:

```text
EvaluationRecord
  -> load/crop/resample mono audio at 16 kHz
  -> VAD
  -> diarization
  -> segmentation
  -> ASR for each segment
  -> speaker embedding
  -> cosine matching
  -> apply diarization labels where applicable
  -> assemble PipelineOutput
  -> prediction adapter
  -> existing scoring, plotting, and reporting
```

This differs from a simplistic “VAD then diarization” assumption in an important way: diarizer turns can become the actual segmentation source. Provenance must state whether segmentation came from full-record input, VAD/VADChunker, or the diarizer.

## Environment and asset findings

- Core CPU: Python 3.12.7, PyTorch 2.11.0 CPU, `pip check` clean.
- Core CUDA: Python 3.12.7, PyTorch 2.11.0+cu128, CUDA available, RTX 3080, `pip check` clean.
- Measured Stage 8 peak VRAM: Tiny 228,704,256 bytes; Base 448,299,008; Small 1,475,008,512; ECAPA 153,949,696.
- Model cache contains Whisper Tiny, Base, Small, and ECAPA assets. Runtime implicit downloads remain prohibited.
- Extended local, ONNX, WeNet, and WeSpeaker environment profiles are present. The credential-diarization interpreter is absent and NeMo is not installed.
- No API key is required for core Whisper, Energy/Silero VAD, ECAPA, cosine matching, or the locally qualified open backends. pyannote and Picovoice Falcon require separate authorization/credentials and must remain unavailable until the owner supplies them through the documented environment mechanism. The framework must not acquire credentials automatically.

## Benchmark and RIR findings

The benchmark contract uses seed 3800 and authoritative versioned Parquet manifests. Source tiers currently contain:

| Tier | Rows | Controlled clean | Native robustness | Total duration |
|---|---:|---:|---:|---:|
| Small | 405 | 165 | 240 | 2,208.623880 seconds |
| Standard | 2,083 | 760 | 1,323 | 10,843.437575 seconds |
| Large | 8,258 | 1,960 | 6,298 | 38,897.208099 seconds |

Every recorded shortfall has a reason. These are realized manifests, not promises that every planning target was available in normalized metadata.

The current RIR scope is Dining room, Bedroom, and Restaurant. Dining and Restaurant resolve to exact approved files and SHA-256 identities. Bedroom remains unresolved among candidate files and therefore has no executable scenario. Kitchen remains recorded as unresolved historical input, and `h044_ParkingLot_4txts.wav` remains ParkingLot only; it is never represented as Kitchen. The collection inspection found 270 WAV files despite the source label referring to 271. No RT60/EDT/C50/C80 analysis is required in the current scope.

## Artifact and data-integrity findings

The artifact registry defines typed exchange formats and explicit producer/consumer, schema, checksum, privacy, and conditionality rules. No pickle exchange format is used. Completion is based on the resolved scenario profile, status, schemas, counts, checksums, and absence of unresolved temporary files.

Real Stage 1 Whisper Tiny/Base outputs preserve `recording_id`, `source_recording_id` in diagnostics provenance, `utt_id`, and segment timestamps. Successful no-text output is represented by an explicit empty string. Failed items have separate failure/diagnostic records. Prediction speaker identity was not copied from the reference. Alternate unknown tokens normalize to literal `Unknown` while preserving the source token diagnostically.

Speaker Stage 10 outputs use typed embeddings and indexes, bind enrollment to backend/model/config/dimension/preprocessing identity, keep calibration and evaluation separate, and preserve `Unknown` as a scored decision. The inspected smoke is intentionally tiny and clean: two enrolled speakers, two known probes, and one held-out unknown probe. It is contract evidence, not a publishable EER or robustness result.

The Stage 11 Sherpa artifact has valid RTTM/UEM output and explicit scoring policy. Its one-item DER/JER result is a contract smoke only. A warning records that hypothesis RTTM extended beyond the UEM and was clipped; that warning must not be removed or interpreted as a perfect scientific result.

## Executor, resume, and distributed-operation findings

The executor uses deterministic ordering, atomic state changes, leases, heartbeats, stale-running recovery, stop requests, timeout and retry policy, OOM classification, disk checks, partial preservation, and checksum-aware skip-completed behavior. Retry does not change scenario identity unless a result-affecting setting changes.

Worker assignments can select explicit IDs, ranges, component combinations, panels/datasets, deterministic partitions, and maximum counts. Independent copied repositories are the supported two-machine model. Shared SQLite over a network drive is intentionally not used. Transfer and merge validate campaign, benchmark, scenario, component/model/config, seed, schema, checksum, and environment evidence; conflicting duplicates cannot silently overwrite canonical results.

F-01 weakens this area under transient Windows sharing locks until corrected.

## Telemetry findings

CPU telemetry works without NVIDIA tooling. Unsupported values are null with availability reasons. The inspected synthetic executor artifact contains 112 typed samples with process/system CPU and memory, disk counters, disk free space, GPU identity/utilization/memory/temperature/power fields, process tree, timestamps, and sampling-gap flags. It also records that the child process did not produce component spans rather than inventing them.

Stage 8 proves real CUDA model execution and peak VRAM for the core stack. It does **not** replace the skipped Stage 5 real CUDA-event timing smoke. CUDA component-boundary timing and sensor behavior therefore remain limited until that smoke is executed in the CUDA telemetry environment. Multiple simultaneous GPU scenarios are not qualified.

## Metrics, statistics, plots, and analysis findings

Detailed stage analyzers implement more metrics than the campaign-level Stage 12 headline registry. Formula and denominator tests passed for ASR, VAD/segmentation, speaker protocol, diarization, reliability, and paired comparisons. Missing and failed outputs remain in reliability denominators. DER/JER and reference-dependent VAD metrics are suppressed when references or timebases are incompatible.

The Stage 12 registry exposes 19 headline metric families and 20 eligibility-gated plot definitions. A complete synthetic two-worker trace generated a validated four-scenario index, all metric availability records, two eligible plots, and 18 explicit skip records. This proves release mechanics, not model quality.

Current analysis limitations:

- No completed small, standard, or large scientific campaign exists.
- The campaign-level registry does not expose every detailed Stage 7/10/11 metric as a headline analysis metric.
- The plot registry lacks dedicated resource timelines, latency distribution/ECDF, failure funnel, diarization timeline, and subgroup forest plots.
- The analysis CLI does not currently provide command-line selectors for arbitrary metric/plot subsets, row filters, or table-only export; it operates from the campaign root, comparison specifications, and prerequisite evidence.
- Statistical conclusions remain ineligible until the required paired observations, repetitions, and reference compatibility exist.

These are substantial scope limitations but do not invalidate the typed results or analysis-manifest mechanics that are implemented.

## Corrections and re-validation

### F-01 — transient Windows sharing violation during atomic publication — resolved

- **Original severity:** release blocker for unattended Windows campaigns.
- **Observed:** the full automated suite reported one failure in `test_byte_identical_duplicate_is_recognized`. Publishing `failures.parquet` raised WinError 32 (“file being used by another process”) at `os.replace`; temporary-file cleanup then encountered the same lock.
- **Reproduction:** 226 passed, 2 skipped, 1 failed in the combined suite; the exact test passed alone (1 passed), consistent with a transient file scanner/indexer/handle race.
- **Requirement affected:** A10, A14, A27.
- **Approved correction boundary:** bounded retry with short backoff only for recognized transient Windows sharing/access violations during atomic replace and cleanup. Do not change schemas, target names, checksums, completion semantics, or overwrite policy.
- **Changed files:** `app/artifact_contracts/atomic.py` and `tests/automated_evaluation/test_stage3_artifact_contracts.py`.
- **Correction:** atomic replace retries only recognized Windows error codes 5, 32, and 33 over a bounded 1.575-second backoff window. Temporary-file cleanup uses the same bounded handling and no longer masks the primary publication exception. Non-Windows and non-transient errors retain immediate failure semantics.
- **Focused validation:** injected one-time WinError 32, interruption-before-replace, and the previously failing duplicate test: 3 passed.
- **Affected validation:** Stage 3/4/5/6/12 tests: 85 passed, 1 skipped (core interpreter CUDA timing).
- **Full validation:** `tests/automated_evaluation`: 228 passed, 2 skipped, 2 third-party deprecation warnings in 362.03 seconds. Skips were the real CUDA-event timing smoke in the CPU interpreter and WebRTC qualification in the core interpreter; both have explicit profile boundaries.
- **Protected regression:** 331 passed, 2 third-party deprecation warnings in 23.01 seconds.
- **Static validation:** Ruff check and formatting passed for both changed Python files.
- **Artifact inspection:** corrected full-suite Stage 6 and Stage 12 flows completed atomic Parquet publication, two-worker merge, result indexing, and synthetic release analysis without stale temporary files or checksum conflict.
- **Disposition:** resolved within approved scope.

### F-02 — consolidated operator documentation was absent — resolved

- **Severity:** acceptance documentation blocker, not a runtime defect.
- **Observed:** phase-specific documentation exists, but there is no current owner/operator guide or quick command reference. Older root architecture documents describe pre-integration planning and can mislead an operator.
- **Requirement affected:** A24.
- **Approved correction boundary:** create the required system guide, quick reference, Phase 13 report, README navigation, and a clear historical notice on superseded architecture text after this final verdict. Correct stale current-workflow command/profile names. Do not invent unsupported commands or capabilities.
- **Correction:** after this audit contained its final verdict, the system guide, quick reference, current architecture map, README navigation, historical notices, and Phase 13 report were created or updated.
- **Disposition:** resolved by the post-verdict documentation validation below; the technical verdict is unchanged.

## Regressions

No protected functional regression was found. Fresh protected tests passed 331/331, and the GUI validation harness passed. F-01 is an additive automated-artifact reliability defect, not a demonstrated regression in legacy simulation/external runner/GUI behavior.

## Unqualified or blocked components

- WeNet ASR: required model asset (`final.zip`) unavailable.
- pyannote diarization: authorization/token and licensed model access not configured.
- Picovoice Falcon: access key and licensing prerequisites not configured.
- NeMo diarization: Windows/platform and model-asset qualification blocked.
- WebRTC VAD and WeSpeaker embedding: available only with recorded warnings.
- Stage 5 real CUDA-event telemetry smoke: not completed.
- Dual-GPU-job concurrency: not qualified and must remain disabled by default.

## Documentation work completed after this verdict

- The owner/operator system guide and quick reference now exist.
- README navigation identifies this audit as the limitation source of truth.
- Current worker examples use the Stage 8 profile spelling `core-cpu`; the Stage 0 `core_cpu_development` identity remains only where historical contracts/tests require it.
- Historical architecture/readiness documents have visible notices pointing to current documentation.
- The worked end-to-end campaign trace is explicitly synthetic and is paired with a separate fresh real Whisper Base evaluator trace.

## Preliminary verdict history

The preliminary verdict was **`not_release_ready`** while F-01 remained open.

That verdict correctly prevented handbook publication before the unattended Windows reliability defect was fixed. The correction and full re-validation above satisfy the blocker.

The preliminary verdict must not be read as a claim that existing artifacts are invalid. Existing checksum/schema-valid results remain usable within their stated smoke, synthetic, or qualification scope.

## Final release recommendation

**Final verdict: `release_ready_with_documented_limitations`.**

The framework contracts, core workflows, protected existing behavior, atomic artifact exchange, resume and distributed mechanics, qualification paths, and synthetic release analysis are accepted for owner/operator use within the boundaries in this audit. The repository is not accepted as evidence of a scientifically best speech pipeline because no small, standard, or large release campaign has been completed.

Before making model-selection or production-quality claims, the owner must:

1. resolve and freeze an exact Bedroom RIR if Bedroom reverberation is required;
2. run the real Stage 5 CUDA-event telemetry smoke in the `core-cuda` interpreter;
3. run the small release gate, inspect it, then advance through standard and large only when eligible;
4. retain the default of one GPU-heavy scenario at a time until a separate concurrency qualification passes;
5. supply and authorize credentials/assets personally for any blocked backend, without storing secrets in artifacts;
6. treat fixed matcher thresholds and all bounded smokes as contract evidence rather than calibrated deployment performance.

The owner/operator handbook may now be written using this audit as its source of truth.

## Post-verdict documentation consistency validation

The handbook was produced only after the final verdict above was present.

- `docs/automated_evaluation/system_guide.md`: complete owner/operator manual with actual architecture diagrams, environments, components, campaigns, distributed work, artifacts, metrics, plots, troubleshooting, state reference, reproducibility, and limitations.
- `docs/automated_evaluation/quick_reference.md`: concise command workflows.
- `docs/automated_evaluation/current_evaluation_tool_architecture.md`: compact source and contract map.
- README navigation was added to the Evaluation Tool and automated-evaluation documentation index.
- Historical root documents were marked historical rather than silently rewritten.
- A parser-level documentation audit checked 81 `run_evaluation.py` command lines across 28 distinct real command paths and found no unknown command or option.
- A final link/path audit checked 29 local Markdown links and seven documented scripts/configs/catalogs; all resolved.
- Registry consistency checks confirmed 27 runtime components, eight Stage 8 profiles, 19 campaign headline metrics, 20 plot definitions, 12 executor states, and the exact quick-start scenario identity/content.
- The exact one-item guide command ran successfully through configured Whisper Base, existing scoring, 11 existing plots, and reporting: one selected item, one prediction, zero failed/missing items, WER 0.25. The retained evidence is `runs/20260808_094235_cmu_arctic_full_base_one_item`.
- The handbook states every limitation in this audit and does not promote smoke/synthetic evidence to a scientific conclusion.

Documentation readiness is accepted. The final verdict remains **`release_ready_with_documented_limitations`**.

## Stage 14 operational-readiness addendum — 2026-08-10

The Phase 13 verdict above remains the acceptance of the framework contracts.
It is **not** launch authorization for the scientific massive campaign. Stage
14's narrower operational verdict is **`NOT_READY_TO_LAUNCH`**, as recorded in
`operational_launch_readiness.md` and `launch_control_sheet.md`.

The audit base remains commit
`4e1c1e7cea17bfdea87f4af6c4ae1d23d5052f44`. Stage 14 source, tests,
configuration, scripts, and documentation are currently uncommitted. Therefore
that commit must not be represented as containing this launch package. A new
reviewed commit, post-commit runtime binding on both clean clones, and another
genuine clean-clone validation are mandatory before launch. Runtime binding is
used because a tracked file cannot contain the hash of the commit that contains
that same file without creating a circular identity.

### Operational corrections

| Finding | Root cause and observed impact | Correction / changed files | Verification |
|---|---|---|---|
| `P14-OP-001` — iterator exhausted during final publication | JSONL readers return iterators, but final publication counted and reused them; a real completed evaluator pass could fail at artifact publication | Materialize prediction, diagnostic, and failure streams once in `app/campaign_executor/runtime.py`; regression in `test_campaign_runtime_publication.py` | Included in focused and full suites; real install smoke publishes complete artifacts |
| `P14-OP-002` — assignment validation assumed artifact registry v1 | A v2 campaign could fail worker assignment validation despite a valid recorded registry | Resolve the campaign-recorded registry in `app/campaign_exchange/assignments.py`; Stage 6 regression | Frozen v2 massive assignments validate 20+21, no overlap/missing |
| `P14-OP-003` — idempotent analysis re-index could replace an identical immutable contract | A needless Windows replace could fail under a transient indexer/antivirus handle | Retain byte-identical contracts and still reject changed content in `app/campaign_analysis/index.py`; Stage 12 regression | Repeated analysis-index test passes on Windows |
| `P14-OP-004` — controlled `stopped` work had no explicit route back to pending, and generic resume was unsafe for two workers | Operators could stop safely but could not resume that work without manual state intervention; a global action risked touching another assignment | Add explicit `stopped → pending`, `resume_stopped`, CLI support, and assignment-scoped `--resume-stopped` in state/CLI/exchange execution; update READMEs | Stage 4/6 tests prove only the selected assignment is requeued; bounded real stop/resume rehearsal passed |
| `P14-OP-005` — portable `RawDatasets` metadata anchor did not resolve an accepted local raw-data alias | Genuine clean-clone real inference failed although the operator-supplied dataset existed under `Raw Datasets (Not formatted)` | Preserve the public metadata path while resolving an existing approved alias in `app/utils/paths.py`; path regression | Clean-clone CMU Arctic Base run then produced one prediction, metrics, 11 plots, and report |
| `P14-OP-006` — Stage 6 JSON/YAML atomic writer lacked bounded Windows sharing-lock retry | Complete 20-scenario preflight inspection succeeded but publishing its replacement JSON raised WinError 5 | Reuse public bounded file replacement/cleanup helpers from `app/artifact_contracts/atomic.py` in `app/campaign_exchange/common.py`; Stage 3/6 lock regressions | Injected WinError 5 and 32 tests pass; full A preflight now publishes successfully |
| `P14-OP-007` — final commit identity was self-referential | Updating a tracked package to contain the commit that includes its own update would always create another commit hash | Keep candidate evidence immutable; add deterministic `--bind-current-commit` materialization and ignored `release_binding.json` containing both final assignment identities | Stage 14 regression binds both assignments to a simulated new HEAD, retains all 41 IDs, and reports zero overlap |

### Revalidation after corrections

- Final automated-evaluation suite: **242 passed, 2 expected skips**, two
  third-party deprecation warnings, 233.03 seconds.
- Protected non-automated suite: **337 passed**, two third-party deprecation
  warnings, 12.74 seconds; GUI validation harness passed.
- Final Stage 3/6/14 set: **55 passed**; broader pre-binding Stage
  4/6/12/14/runtime/path set: **64 passed**.
- Ruff check passed for every changed Python file; new Stage 14 Python files
  also pass Ruff formatting checks. `pip check` reports no broken requirements.
- All seven launch PowerShell helpers parse successfully.
- All six campaign roots validate: install smoke 1, component canary 15,
  two-worker shakedown 2, small 26, standard 41, massive candidate 41.
- Frozen materialization reproduces campaign SHA-256
  `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4`
  and assignments `assignment_5014479496c7` (20) and
  `assignment_53642fa92b2a` (21), with zero overlap and zero missing IDs.
- Machine A's strict full assignment preflight inspected **20/20 scenarios,
  12,368 item executions, and 2,750 unique audio files**. Every scenario-
  specific input, header/bound, component, model, RIR, pipeline, RAM, disk, and
  output check passed. The assignment correctly remains blocked by the dirty
  candidate tree and missing FFmpeg.
- Machine B remains `NOT_YET_TESTED`. Its 21-scenario assignment passed a
  complete static cross-check on A (13,430 item executions and 2,622 unique
  source files), but no B hardware, environment, local data, output, disk, or
  runtime claim is made.

### Launch-gate disposition

The genuine remote clean clone at `4e1c1e7…` created a new environment,
verified Whisper Tiny/Base/Small and ECAPA assets (25/26 verifier checks; only
FFmpeg missing), and completed one real CMU Arctic → Whisper Base → prediction
→ scoring → plots → report run. This validates the committed core workflow
with manual data/model setup, but not the uncommitted launch package.

The 41-scenario massive candidate is a Whisper Base CPU full-record reference
and robustness surface. It is not a multi-backend finalist campaign and cannot
support component-selection claims. Component canary execution, small and
standard scientific gates, finalist selection, Stage 14 commit/freeze, FFmpeg
on A, and the actual Machine B profile/full preflight remain mandatory. The
Phase 13 framework acceptance therefore coexists with the Stage 14 operational
verdict **`NOT_READY_TO_LAUNCH`**.
