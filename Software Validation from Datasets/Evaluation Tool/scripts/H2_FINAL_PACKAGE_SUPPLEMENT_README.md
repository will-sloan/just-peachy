# H2 final-package presentation supplement

## Purpose

`augment_h2_final_package.py` closes the final presentation-package requirement
without changing the frozen scientific campaign. It runs only after the native
H2 controller has produced and validated its compact ZIP.

The tool:

1. fully validates the native ZIP with the frozen H2 package validator;
2. leaves every native package member byte-for-byte unchanged;
3. derives SVG plots from final immutable CSV tables;
4. adds the checksum-bound Phase 1 axis-selection receipts;
5. derives the four explicitly required diarization metric families that are
   absent from the central catalog—cluster purity, short-turn recall,
   clean-evidence yield, and time to clean evidence—from checksum-valid saved
   RTTM/reference results;
6. gives every computed supplemental metric a deterministic 2,000-repetition
   whole-speaker bootstrap interval and keeps development and held-out evidence
   separate;
7. reconstructs all four frozen paragraph policies and adds the explicitly
   required transcript-structure metrics: over/under-segmentation proxies,
   mixed-speaker paragraphs, words per paragraph, structural paragraph
   revisions, word-level attribution, final stability, and a disclosed
   readability proxy;
8. derives an overlap-policy table stratified into all-known, mixed known/
   unknown, and all-unknown speaker compositions, each split into overlap-
   present cases and matched no-overlap controls, with the same deterministic
   whole-speaker uncertainty method;
9. pairs the immutable 0, 250, 500, 750, and 1,000 ms boundary-correction
   results and reports repaired words, harmed words, wrong-to-other-wrong
   moves, previous-speaker assignments, word accuracy, boundary delay,
   UI-visible speaker relabels and their audio/compute dwell, transcript
   revisions, final stability, and wrong-name dwell. Exact word-time in seconds
   is explicitly unsupported because the references do not contain word
   timestamps; it is never estimated from segment duration;
10. copies the six byte-exact, checksum-verified development science tables for
   open-set policy calibration, identity hubness, integrated enrollment,
   enrollment quality control, integrated hubness, and the selected enrollment
   cell, preserving their development/evaluation firewall;
11. waits for the storage guardian's terminal pass, preserves the native ZIP's
   pre-publication controller snapshot, adds the exact checksum-bound terminal
   controller state written after native ZIP validation, validates every signed
   prune/compression receipt and nested validation signature, and packages the
   compact artifact-lifecycle map, final forecast, guardian pass, guardian
   code/tests/instructions, and exact reconstruction receipts without embedding
   the removed restart payloads. The snapshot also validates and includes the
   signed CPython 3.12 Linux ARM64 wheel-resolution map while excluding every
   wheel payload; it binds the deployment requirements and frozen runtime
   identity carried by the same ZIP. The snapshot also validates the bounded
   Windows atomic-publication retry policy, its exact launcher hash, instructions,
   and compact event log; this records operational recovery without changing the
   frozen scientific runtime. It also exports every durable queue attempt to
   a compact checksum-bound CSV, including transient failures that later
   recovered, so a successful final job cannot hide its earlier attempts.
   Post-selection dynamic-execution manifests are also copied and checksum-
   validated so every dynamic receipt resolves back to its frozen logical job;
12. validates and adds a signed 100-sample controlled engineering benchmark of
   event-emission-to-Tk-presentation latency. The measurement exercises the
   durable JSONL cursor, coalescing UI queue, background worker-to-Tk handoff,
   state projection, and real widgets. It includes the exact exercised runtime
   sources and explicitly excludes neural inference, microphone performance,
   operating-system compositor delay, and physical display scanout;
13. validates and adds the compact signed pre-open enrollment/data-firewall
   audit. It proves development/evaluation separation across enrolled speakers,
   reserved clips, audio hashes, case identities, and gallery membership, and
   records that all held-out jobs were still pending with zero attempts. Exact
   source-manifest hashes and the audit code/test/runbook are retained without
   embedding audio, biometric templates, or the large case manifests;
14. recomputes frozen final-transcript WER exactly from each checksum-valid
   baseline/held-out result, adds a matched ASCII-punctuation-insensitive
   cross-protocol rescore over the same immutable hypotheses, stratifies it by
   speaker count and overlap, reports the punctuation-sensitive minus
   punctuation-insensitive WER gap, and measures the share of reference and
   hypothesis tokens containing ASCII punctuation. These punctuation-emission
   diagnostics are not presented as punctuation precision or causal error
   attribution. Endpoint-window `final_wer` remains explicitly separate. The
   rescore is diagnostic only: it never changes native metrics, development
   selection, the held-out firewall, or neural inference;
15. validates and packages the checksum-bound Phase-1 Windows host-I/O receipt,
   exact collector, and runbook; independently recomputes each candidate's
   event-time bucket and maximum OS I/O delay; exports all four queue summaries
   and their largest case stalls; and records that accuracy/promotion remain
   eligible while accuracy-run wall time, RTF, and queue blocking are ineligible
   for resource comparison. Temporal coincidence with Acronis/VSS is retained
   without claiming that one process was the sole cause;
16. validates both matched serial-resource groups and fails closed unless all
   five resource jobs have clear host-I/O evidence. If the original Phase-2
   R1/R2 interval is contaminated or unverified, it discovers the first
   lexicographically named *eligible* quiet replay, verifies its original
   protocol/job/runtime/result lineage, exact R1-then-R2 order, clean Windows
   event interval, comparison checksum, and source-result preservation, then
   packages that replay as the eligible Phase-2 resource evidence. The original
   contaminated receipt remains in the ZIP and is never overwritten or silently
   dropped. Phase 6 must still be clear in the main campaign;
17. preserves and validates the signed disclosure for the accidental diagnostic
   CPU load observed during the post-promotion development integration run. It
   binds the affected job, protocol, manifest, frozen runtime, process intervals,
   and cleanup evidence; marks that attempt's timing/resource fields ineligible
   as clean deployment evidence; records that promotion had already completed;
   and requires the clean serial resource/replay evidence instead. No completed
   accuracy work is deleted or silently reclassified;
18. preserves the frozen `deployment/h2_arm64/` bundle byte-for-byte while
   adding `deployment/h2_arm64_v2/` as an explicit deployment-only
   supersession. V2 quotes systemd paths containing spaces, points systemd and
   Docker to the v2 launcher, and applies an offline wheelhouse to both the
   pinned pip bootstrap and runtime dependencies. Its receipt records that no
   scientific result or policy changed and real ARM64 hardware is unvalidated;
19. adds a deployment-only comparison of Raspberry Pi Compute Module 5 and the
   Arduino UNO Q 2 GB/4 GB variants. It combines official board/runtime
   specifications with the immutable desktop serial RSS/RTF and ARM64
   portability results, but does not extrapolate desktop timing to either ARM
   CPU, credit unsupported Qualcomm acceleration, claim hardware validation, or
   change the desktop scientific ranking. The report binds the exact UNO Q
   variant datasheet and requires the intended CM5 cooler/enclosure during the
   sustained-load qualification;
20. adds a checksum-bound Phase-0 streaming-execution disclosure. It verifies
   that the common causal coordinator, native partial/final ordering, terminal
   trace completeness, external-media timing, blocking queue, and zero-drop
   evidence are present, while explicitly recording whether ASR was freshly
   decoded or replayed from a native stateful trace. It prevents accelerated
   file simulation from being presented as a physical-microphone, real-time
   1.0x, resource, or ARM64-hardware measurement. The same disclosure also
   validates all three post-selection serial resource result trees, their
   execution-contract identities, and their isolated cache regimes; those jobs
   must show fresh native ASR compute with stream-trace replay disabled. Neither
   evidence class alters selection;
21. packages and independently revalidates the complete pre-freeze selector-
   correction handoff: the signed activation manifest and receipt, original and
   patched controller sources, both focused tests, staging validation, conflict
   audit, atomic-publication launcher, and runbook. Every manifest file binding
   must match its packaged bytes, the two prerequisite development results must
   remain complete, and the frozen policy must contain the exact correction
   identity. The receipt must prove activation occurred while held-out evidence
   was unopened and that the prepared inference-runtime identity and qualified
   R3 scientific selection were preserved;
22. creates a deterministic augmented ZIP with a new full manifest and checksum
   inventory, including the augmenter source, both post-run watchers, focused
   tests, and this runbook so the post-run derivation itself is reproducible;
23. validates the augmented ZIP and writes a receipt containing the upload path
   and SHA-256 hash.

The supplement also pairs every predeclared 30-minute long stream with its
60-minute stream from the same source recording. It reports explicit drift in
RTF, peak RSS, maximum queue depth, normalized dropped frames, normalized text/
identity/cluster revisions, and every bounded session-state cardinality.
Development and held-out pairs remain separate. Temperature drift is marked
unsupported because the desktop runtime does not emit temperature telemetry.

It also adds the three explicitly requested final operating roles—desktop
reference, product-software primary, and 2 GiB ARM64 candidate. The product
primary is mapped from the development-frozen default mode. The ARM64 role
retains the `PORT_REQUIRES_WORK` and not-hardware-validated boundary. These
recommendations are checksum-bound presentation metadata and cannot retune or
replace any native scientific result.

The plots are presentation derivatives. They do not alter measurements,
thresholds, selections, conclusions, or the original validated ZIP.

The complete synthetic-package test fixture follows the same mandatory
two-snapshot contract: the native ZIP contains the controller's `RUNNING`
collection snapshot, while the storage supplement contains the later terminal
state. It also creates signed storage lifecycle/forecast/guardian evidence, a
signed prune receipt, and development dynamic-execution bindings.
Tests therefore exercise storage provenance instead of bypassing it.

The metric supplement is also post-run and inference-free. It validates each
source result tree and controller/registry/result hash before reading saved
RTTMs. The historical H2 baseline remains development-only, each optimized mode
uses only its untouched held-out result, and the ONNX candidate is explicitly
reported as parity-only rather than inheriting native scores.

The transcript supplement replays immutable final transcript spans and saved
`transcript_revision` events through a dictionary implementation tested for
equivalence with the frozen `ParagraphManager`. Development T1–T4 policy
comparisons and held-out optimized-mode results remain separate. Because the
installed references contain utterance/turn boundaries rather than human-
authored paragraph annotations, over/under-segmentation are explicitly reported
as 0.50-second non-overlap reference-turn-boundary proxies. The readability
proxy is fully defined in the output and is descriptive only; it does not alter
the frozen policy selection.

## Inputs

- Native controller-produced H2 final ZIP under
  `JustPeachyResearchSummaries`, or an explicit `--source-zip`.
- Final controller workspace, normally
  `automated_runs/h2_complete_product_pipeline_v17`.
- Signed controlled UI-latency receipt under the workspace's
  `engineering_validation/ui_event_latency_receipt.json`. It must bind the
  exact frozen runtime identity carried by the native ZIP.
- Signed pre-open enrollment/data-firewall receipt under
  `engineering_validation/enrollment_firewall_audit_receipt.json`. It binds the
  prepared protocol manifests, split registries, frozen runtime, and unopened
  held-out queue using compact SHA-256 metadata only.
- Checksum-bound host-I/O receipt under
  `diagnostics/host_io_interference/windows_host_io_interference.json`. It must
  bind the four Phase-1 medium jobs, their complete result checksum inventories,
  the frozen development promotion, and the matching protocol/job manifest.
- Clear serial-resource receipts under `diagnostics/host_io_interference` for
  Phase 2 (R1/R2) and Phase 6 (the three selected product modes). When the
  original Phase-2 receipt is contaminated or unverified, the packager requires
  a completed eligible replay created by
  `scripts/replay_h2_phase2_serial_resources.py`. The replay workspace and
  summary must use the standard
  `<campaign>_resource_replay_<attempt-id>` names on C:. Its exact replay
  manifest, sanitized controller state, frozen job manifest, clean receipt,
  comparison JSON/CSV, launcher, and runbook become checksum-bound package
  inputs. A claimed-eligible but incomplete or tampered attempt fails closed.
- These immutable package tables:
  - `summary/h2_mode_comparison.csv`;
  - `summary/h2_resource_results.csv`;
  - `summary/h2_segmentation_frontier.csv`.
- Immutable `summary/h2_memory_budget.json` and
  `summary/h2_linux_portability.json`, plus the configuration registry, provide
  the measured desktop boundary for the hardware comparison. Board facts are
  bound to the official Arduino UNO Q 2 GB/4 GB documentation, official
  Raspberry Pi Compute Module 5 documentation, official Sherpa-ONNX Linux
  aarch64 documentation, and official ONNX Runtime QNN documentation. The
  report is regenerated after the campaign; it does not inspect or modify a
  running evaluation.
- Native `controller/program_state.json` (the intentional pre-publication
  collection snapshot), the terminal workspace `program_state.json`, and the
  matching checksum-bound files under the workspace's `axis_selections`
  directory. Immutable program/protocol/path fields must match across both
  state snapshots.
- The checksum-bound files under
  `diagnostics/pre_freeze_selector_fix_staging`, the signed
  `diagnostics/pre_freeze_selector_correction_activation.json`, and the frozen
  policy's `pre_freeze_selector_correction` binding. The packager requires the
  activation manifest, receipt, original/patched sources, tests, validation,
  and conflict audit to agree byte-for-byte; it does not reactivate or rerun
  the correction.
- The result directories bound by `summary/h2_configuration_registry.yaml` and
  final controller state. Required inputs are the immutable
  `references/cases.jsonl`, `predictions/diarization.rttm`, source reference
  RTTMs, and their complete checksum inventories.
- `protocol/job_manifest.json`, which identifies the four development-only
  T1–T4 runtime jobs, plus each bound result's labelled transcript, supported
  speaker-attributed reference transcript, event log, ASR metric file, pipeline
  identity, and checksum inventory.
- The exact Phase-0 `H2_TRUE_STREAMING_QUALIFICATION` manifest row, completed
  controller result binding, checksum-valid cache regime, case-status queue
  evidence, pipeline execution contract, and compressed event log. These inputs
  are used only to disclose fresh-decode versus native-trace-replay provenance,
  pacing, input clock, queue behavior, and the limits of the qualification.
- The two development-only overlap-axis jobs identified by the frozen manifest,
  including checksum-bound `diagnostics/per_case_metrics.jsonl`,
  `references/cases.jsonl`, pipeline identity, and the selected overlap-policy
  receipt. The builder requires identical ordered case sets and verifies that
  only the overlap policy differs.
- The five development-only boundary-correction jobs identified by the frozen
  manifest. Their result trees must contain checksum-bound cases, reference
  transcripts and overlays, final labelled transcripts, diarization RTTM,
  per-case metrics, pipeline identity, and compressed event logs. Ordered case
  sets and reference payloads must be identical, and both manifest and result
  identities must prove that only `boundary_correction_ms` varied.
- The completed `policy_replay` and `integrated_enrollment` job results bound by
  controller state, including their artifact manifests and six source CSVs.
- The terminal `storage_maintenance` snapshot: signed artifact lifecycle, final
  forecast, final guardian pass, all final prune receipts, any v14 active
  long-session compression receipts, and no pending receipt. Every
  `campaign.sqlite3` below the controller workspace is read after terminal
  completion to export its complete attempt history without embedding the
  database. The watcher waits until this snapshot is newer than the terminal
  controller state.

## Outputs

- `<native-package-name>_with_plots.zip`;
- `<augmented-zip>.receipt.json`;
- `automated_runs/h2_complete_product_pipeline_v17/final_augmented_collection.json`,
  an atomic workspace pointer to the checksum-validated preferred upload artifact;
- `JustPeachyResearchSummaries/LATEST_H2_AUGMENTED_PACKAGE.json`, an atomic
  package-root pointer carrying the same native and augmented ZIP bindings;
- five SVG plots plus `plots/PLOT_GUIDE.md` inside the augmented ZIP;
- `supplements/h2_required_diarization_metrics.csv`, with explicit definitions,
  denominators, variants, evidence targets, censoring policy, and whole-speaker
  95% bootstrap intervals;
- `supplements/H2_REQUIRED_DIARIZATION_METRICS.md` and the complete checksum/
  split/result provenance JSON;
- `supplements/h2_required_transcript_structure_metrics.csv`, containing ten
  explicit transcript/paragraph rows for each of four development policies,
  three untouched held-out modes, and the parity-only ONNX candidate;
- `supplements/H2_REQUIRED_TRANSCRIPT_STRUCTURE_METRICS.md` and its complete
  checksum/split/replay/bootstrap provenance JSON;
- `supplements/h2_asr_wer_comparability.csv`,
  `supplements/H2_ASR_WER_COMPARABILITY.md`, and the matching provenance JSON,
  retaining frozen punctuation-sensitive WER, adding an inference-free
  punctuation-insensitive cross-protocol diagnostic, reporting their WER gap
  plus reference/hypothesis ASCII-punctuation token rates, and declaring
  endpoint `final_wer` non-comparable to ordinary exported-transcript WER because a
  reference turn crossing an endpoint can be mapped in full to both adjacent
  endpoint windows. The CSV also
  separates single-speaker, 2–4-speaker, 5–12-speaker, overlap-present, and
  no-overlap strata without pooling development and held-out evidence. The
  earlier Common Voice normalization YAML is embedded with its checksum rather
  than being described from memory;
- `supplements/h2_queue_backpressure_summary.csv`,
  `supplements/h2_queue_backpressure_cases.csv`, and
  `supplements/H2_QUEUE_BACKPRESSURE.md`, preserving the four checksum-valid
  development candidates, zero-drop evidence, per-job Windows-event
  correlation, and the explicit accuracy-valid/resource-timing-invalid scope;
- `reproducibility/host_io/`, containing the sanitized Windows event receipt,
  exact PowerShell collector, run instructions, and a complete provenance
  inventory. The validator independently reconstructs the per-job timestamp
  buckets so a timezone or dictionary-sorting error cannot silently survive.
  When Phase-2 replay is necessary, its
  `phase2_quiet_replay/` child preserves the original contaminated receipt and
  adds the sanitized replay manifest/state, frozen job manifest, clean replay
  receipt, matched comparison, launcher, instructions, and signed binding;
- `supplements/h2_overlap_stratified_results.csv`, containing 96 rows: two
  executable policies × three identity compositions × overlap-present/control
  conditions × eight required metrics, including availability counts and 95%
  whole-speaker bootstrap intervals;
- the known/unknown composition consumes the protocol's canonical
  `MIXED_KNOWN_UNKNOWN` overlay label rather than a fixture-only abbreviation;
- multi-speaker mixed cases require both enrolled and unenrolled active
  speakers, while deterministic one-speaker controls may contain either state
  and remain in the nominal mixed-overlay stratum;
- overlap-present versus control membership follows measured reference
  `overlap_ratio`; an intended backchannel clip with zero realized simultaneous
  reference speech is reported as a no-overlap control, with the intended class
  retained in the checksum-bound source case;
- `supplements/H2_OVERLAP_STRATIFIED_RESULTS.md` and its checksum-bound source,
  selection, composition, split-firewall, and derivation provenance JSON;
- `supplements/h2_boundary_correction_summary.csv`, with one aggregate row for
  each 0–1,000 ms correction window and deterministic whole-speaker intervals;
- `supplements/h2_boundary_correction_case_pairs.csv`, preserving every paired
  case's repaired/harmed/previous-speaker counts, source metrics, relabel
  revisions, measured delay sufficient statistics, and unsupported reasons;
- `supplements/H2_BOUNDARY_CORRECTION_DIAGNOSTICS.md` and
  `supplements/h2_boundary_correction_provenance.json`, including the frozen
  selection receipt, five result hashes, critical-file identities, split
  firewall, exact word-alignment code hash, and explicit word-time limitation;
- `supplements/source_science/`, containing byte-exact copies of
  `open_set_policy_frontier.csv`, `identity_hubness.csv`,
  `integrated_enrollment_matrix.csv`, `integrated_enrollment_qc_events.csv`,
  `integrated_enrollment_hubness.csv`, and
  `integrated_enrollment_selected_cell.csv`, plus a checksum/result/firewall
  provenance receipt;
- `AUGMENTED_PACKAGE_MANIFEST.json` and
  `AUGMENTED_PACKAGE_CHECKSUMS.json` inside the augmented ZIP;
- copied `controller/axis_selections/*.json` receipts.
- `reproducibility/storage/`, containing the terminal lifecycle/forecast/pass,
  the exact terminal controller state paired with the unchanged native
  pre-publication state,
  every signed prune and v14 compression receipt, the storage guardian and
  supervisor source, the Windows atomic-publication policy/launcher/events,
  focused tests, instructions, all development dynamic-
  execution manifests, `queue_attempt_history.csv` with recovered and terminal
  attempts, and a checksum-bound provenance inventory. Removed restart shards,
  raw audio, queue databases, model weights, and private biometric caches are
  deliberately not embedded.
- `reproducibility/selector_correction/`, containing the signed activation
  receipt and manifest, original and patched controller sources, focused
  controller/bootstrap tests, staging validation, conflict audit, atomic retry
  launcher, and runbook. Its provenance cross-checks every source hash against
  the activation manifest and requires the identical correction binding in the
  signed frozen policy.
- `reproducibility/augmentation/`, containing the byte-exact augmentation
  source, focused test suite, terminal watcher, this runbook, and their
  checksum provenance.
- `reproducibility/ui_event_latency/`, containing the signed controlled
  event-to-Tk receipt, benchmark source/tests/runbook, exact exercised event,
  session, state, and UI sources, and a validated provenance inventory.
- `reproducibility/data_firewall/`, containing the signed pre-open enrollment
  and held-out firewall receipt, exact audit source/test/runbook, and compact
  provenance. Raw audio, embeddings, biometric profiles, and large case
  manifests are excluded; their authoritative source identities remain bound
  by SHA-256 in the receipt.
- `reproducibility/host_interference/development_cpu/`, containing the signed
  post-promotion CPU-interference disclosure and a package-level provenance
  receipt. It makes the affected integration timing fields ineligible while
  preserving the immutable accuracy result and requiring clean serial evidence.
- `supplements/h2_controlled_ui_event_latency.csv` and
  `supplements/H2_CONTROLLED_UI_EVENT_LATENCY.md`, containing the deterministically
  rendered metric summary and its explicit engineering-only scope. These do not
  overwrite the immutable native `h2_ui_latency_results.csv`.
- `supplements/h2_final_recommendations.json` and
  `supplements/H2_FINAL_RECOMMENDATIONS.md`, containing the three required
  operating roles and their frozen-evidence bindings.
- `supplements/h2_hardware_platform_assessment.csv`,
  `supplements/H2_HARDWARE_PLATFORM_ASSESSMENT.md`, and
  `supplements/h2_hardware_platform_assessment.json`, comparing CM5 2 GB and
  4 GB+ separately with UNO Q 4 GB and 2 GB across CPU, RAM, storage capacity
  and fit gates, Linux/runtime compatibility, audio, display, and expected
  pipeline feasibility. The CM5 RAM recommendation is derived only after the
  final matched-serial peak RSS is available. If it remains at or below the
  frozen 1700 MiB risk boundary, the report directs the first lean-ONNX sizing
  test to CM5 2 GB with CM5 4 GB as the safe fallback; otherwise it directs
  initial validation to CM5 4 GB while retaining 2 GB as an optimization
  experiment. It never declares 4 GB scientifically necessary without a failed
  exact-board 2 GB gate. The intended display is explicitly a simple 2D
  transcript/status UI, so RAM sizing is driven primarily by ASR, segmentation,
  the shared ReDimNet worker, audio services, queues, startup/restart spikes,
  and OS/UI reserve rather than graphics compute. UNO Q 4 GB remains a
  secondary portability prototype, and UNO Q 2 GB remains a `PLATFORM_BLOCKER`
  for the complete evaluated native pipeline and therefore only a high-risk
  lean-ONNX experiment. Every row
  remains explicitly `NOT_RUN` on target hardware, and the validator rejects
  any claim of QNN acceleration or a changed scientific ranking. The comparison
  must also bind final serial peak RSS, total RTF, checksum-bound model-asset
  bytes, and measured run-cache bytes. Run-cache bytes are sizing evidence and
  are not presented as permanently required device storage.
- `supplements/H2_STREAMING_EXECUTION_PROVENANCE.md` and
  `supplements/h2_streaming_execution_provenance.json`, distinguishing common
  causal-runtime/native-interaction qualification from fresh decoder compute,
  real-time pacing, physical microphone capture, serial resource evidence, and
  target-hardware validation. The files bind the exact Phase-0 result and all
  three post-selection serial resource results, execution contracts, and cache
  regimes by SHA-256. Resource eligibility requires isolated attempt-local
  execution with ASR trace replay disabled.
- `deployment/h2_arm64_v2/`, containing the complete superseding ARM64
  preparation bundle. The original `deployment/h2_arm64/` remains unchanged as
  frozen v16 provenance;
- `supplements/H2_ARM64_DEPLOYMENT_V2.md` and
  `reproducibility/arm64_deployment_v2/ARM64_DEPLOYMENT_V2_PROVENANCE.json`,
  binding every original/v2 member hash and the deployment-only qualification
  boundary;
- `supplements/h2_long_session_drift.csv`,
  `supplements/H2_LONG_SESSION_DRIFT.md`, and the matching provenance JSON,
  containing source-matched 30-to-60-minute runtime/state drift without any
  additional inference.

The source/native ZIP is never overwritten or deleted.

The augmentation can take roughly 15–60 minutes on the current machine because
it deliberately revalidates complete result inventories and streams saved event
logs for paragraph-revision replay. The exact time depends on the held-out event
log size. This is final packaging work, not new model inference.

## Automatic watcher

The restart-independent scientific controller already performs its native
analysis and collection automatically. A separate read-only watcher can wait
for that exact completion status and then run this presentation supplement.
It never starts, stops, retries, or modifies the scientific campaign.

After controller completion, the watcher also waits for the storage guardian's
terminal checksum-bound pass. This prevents a race in which the final guardian
could prune a late job after the package had already snapshotted its
reconstruction receipts.

It also waits for both the signed controlled UI event-to-render latency receipt
and the signed pre-open enrollment/data-firewall receipt. This prevents an
incomplete augmentation if final collection finishes before those independent
evidence artifacts are available.

The watcher never guesses which native ZIP belongs to the run. It reads the
exact `final_collection.upload_path` and `zip_sha256` from the terminal
workspace `program_state.json`, requires the path to remain below the configured
C: package root, and verifies the SHA-256 before augmentation. Historical H2
ZIPs with newer or unusual filesystem timestamps therefore cannot be selected.

The watcher opens controller and storage JSON snapshots with Windows
read/write/delete sharing. Polling cannot block the controller or storage
guardian from atomically replacing those files.

## One-time graceful transition command

The earlier all-pipeline eight-day controller was transitioned before H2 began
with the implemented controller-level stop below. The resulting
`stop_request.json` is preserved by the H2 evidence audit with reason
`superseded_by_h2_product_decision`. This block is retained for reproducibility;
do not rerun it against the already stopped historical campaign.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action Status -Json
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action Stop -StopReason 'superseded_by_h2_product_decision'
```

Launch the watcher in the foreground:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\watch_and_augment_h2_final_package.ps1 -IntervalSeconds 60
```

Validate its resolved paths and current state without starting the wait loop:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\watch_and_augment_h2_final_package.ps1 -DryRun
```

Launch it as a hidden background helper:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Watcher = (Resolve-Path '.\scripts\watch_and_augment_h2_final_package.ps1').Path
$EscapedWatcher = $Watcher.Replace("'", "''")
$Command = "& '$EscapedWatcher' -IntervalSeconds 60"
$EncodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
  '-NoProfile',
  '-ExecutionPolicy', 'Bypass',
  '-EncodedCommand', $EncodedCommand
)
```

Watcher events are appended to
`automated_runs/h2_complete_product_pipeline_v17/logs/final-package-supplement-watcher.jsonl`.
It plays the standard Windows notification sound after successful publication.
If the machine restarts before completion, use the normal controller `Resume`
command; it relaunches or reuses this watcher, and deterministic augmentation
is safe to repeat.

## PowerShell

Run after the controller reports `COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`:

If the Phase-2 receipt reports `SERIAL_RESOURCE_HOST_IO_CONTAMINATED` or
`SERIAL_RESOURCE_HOST_IO_UNVERIFIED`, first complete the quiet replay exactly as
documented in `scripts/H2_PHASE2_QUIET_RESOURCE_REPLAY_README.md`. The augmenter
then discovers the first eligible attempt automatically; no path or metric is
manually selected.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe'
& $Python .\scripts\augment_h2_final_package.py
```

The command automatically selects the newest native H2 ZIP and prints:

```text
UPLOAD THIS FILE TO CHATGPT:
<absolute augmented ZIP path>
SHA-256:
<hash>
```

When the background watcher performs this step, it independently rereads the
augmentation receipt, verifies the native and augmented ZIP hashes, and writes
the package-root pointer first and the workspace pointer last. The latter is
therefore the terminal commit marker, and the visible monitor verifies both
bindings before announcing the upload file. It deliberately leaves the controller's
terminal `program_state.json` unchanged: that file continues to identify the
native scientific collection, while the separate pointer identifies the
validated presentation/reproducibility superset that should be uploaded.
The normal `run_h2_product_program.ps1 -Action Run` and `-Action Resume`
commands automatically start or reuse this watcher; the explicit watcher
commands remain available for diagnostics and recovery.

To bind an explicit package and workspace:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe'
& $Python .\scripts\augment_h2_final_package.py `
  --source-zip 'C:\path\to\h2_complete_product_pipeline_protocol_timestamp.zip' `
  --workspace 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17'
```

Validate an already generated augmented package without rewriting it:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe'
& $Python .\scripts\augment_h2_final_package.py --validate-only 'C:\path\to\package_with_plots.zip'
```

## Anaconda Prompt or Command Prompt

No Conda activation is required. Use the repository environment directly:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" scripts\augment_h2_final_package.py
```

## Failure behavior

The tool fails without publishing an augmented ZIP when:

- the native package is missing or does not pass its original validator;
- required final CSVs or computed metrics are absent;
- fewer than three evidence-backed plots can be produced;
- a source result tree, controller binding, registry binding, critical result
  file, or source reference RTTM fails checksum validation;
- development and held-out source partitions do not match their predeclared
  roles;
- any of the four required supplemental metric families, 80 predeclared rows,
  or computed whole-speaker intervals is absent;
- any T1–T4 result, transcript/reference/event critical file, exact paragraph
  policy binding, 80-row transcript metric table, or development/held-out
  transcript firewall is absent;
- any baseline or optimized held-out ASR result cannot reproduce its frozen WER
  numerator, denominator, and value exactly; any matched punctuation-insensitive
  rescore lacks its immutable source binding; any speaker/overlap stratum is
  silently converted to zero; or endpoint-window `final_wer` is presented as an
  ordinary exported-transcript WER;
- the host-I/O receipt, collector hash, protocol/manifest/result bindings,
  96 declared candidate checksums, identical references, zero-drop assertion,
  development-promotion firewall, per-job event-time buckets, maximum-duration
  pairing, sanitization boundary, or accuracy/resource eligibility declaration
  differs;
- either serial-resource group is not clear; or a required Phase-2 quiet replay
  is absent, claimed eligible without a clear receipt, uses a different frozen
  job/runtime/case identity or execution order, cannot reproduce its signed
  comparison CSV, alters a source result, omits the original contaminated
  receipt, or fails any packaged member checksum;
- either executable overlap job is incomplete, has a different case set/order,
  varies anything besides the declared overlap-policy axis, lacks one of the
  six composition/control groups or eight metrics, or cannot produce the exact
  96-row development-only table and whole-speaker intervals;
- any boundary-correction job is incomplete, differs in case order or reference
  payload, varies another runtime axis, changes the paired lexical alignment,
  disagrees with its source word-attribution sufficient statistics, or cannot
  produce all five summary rows and all paired case rows without inspecting
  held-out material;
- either required development science job is incomplete, non-development,
  evaluation-contaminated, outside the bound results root, or any required
  source science table differs from its artifact-manifest checksum, row count,
  or required schema;
- the native pre-publication and terminal controller states disagree on an
  immutable program/protocol/path binding, or either state checksum differs;
- the watcher-resolved native ZIP path or SHA-256 differs from the terminal
  controller's exact `final_collection` binding;
- the terminal storage lifecycle/forecast/guardian pass is absent, predates the
  terminal controller state, has a different checksum binding, contains a
  pending prune receipt, or any prune/compression/nested validation signature
  is invalid;
- any pruned job is outside the frozen job manifest, held-out execution overlay,
  or bounded preflight smoke, or its retained-result/job identity differs;
- the storage source-code/README/test inventory, packaged receipt count, pruned
  logical-byte total, queue database identity, attempt-history count, or
  recovered-failure count differs from its provenance manifest;
- the augmentation source/watcher/runbook inventory differs from its embedded
  source-provenance checksums;
- the frozen ARM64 source bundle differs from its runtime-implementation
  identity, any deployment-v2 file differs from its deterministic rendering,
  systemd path quoting or v2 launcher routing is absent, the offline wheelhouse
  does not cover both pip commands, or the v2 receipt claims ARM64 hardware
  readiness;
- the UI-latency receipt signature, frozen runtime binding, recomputed metrics,
  widget proof, exact exercised source hashes, source inventory, or explicit
  no-inference/no-physical-display firewall differs;
- the enrollment/data-firewall receipt signature, frozen protocol/runtime
  binding, source-manifest hashes, zero-overlap assertions, registry/gallery
  relationship, held-out pre-open evidence, or compact source inventory differs;
- the development CPU-interference disclosure signature, protocol/job/runtime
  binding, affected post-promotion job, cleanup evidence, timing-ineligibility
  boundary, clean-resource remediation, or package provenance differs;
- axis-selection receipts do not match controller-state hashes;
- a supplement member would overwrite a native member;
- any native member changes in the augmented ZIP;
- augmented manifest/checksum membership differs;
- CRC, path, duplicate-name, or size validation fails.
