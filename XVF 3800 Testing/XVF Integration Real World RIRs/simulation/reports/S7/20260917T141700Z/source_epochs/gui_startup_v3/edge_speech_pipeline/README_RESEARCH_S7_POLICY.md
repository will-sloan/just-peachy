# Observed S7 policy availability (candidate_v2, opt-in)

This unfrozen candidate adds research_s7_policy.py and narrow integration changes in research_s7.py, research_s6d.py and runtime.py. It does not edit any frozen epoch or change model code, tracker algorithms, source spans, original thresholds, GUI/presentation/beam hooks or default modeled control behavior. The original V3 scheduler drain and original five BoundedWorker methods remain bytecode/AST-equivalent; a new bounded atomic factory is used only by the observed adapter.

Purpose: stop treating modeled neural-lane readiness as newly measured S7 policy availability. Enable explicitly with S7Settings(availability_clock="observed", pacing="absolute"). The default is "modeled". Observed requires absolute source-end pacing and bounded S6D text delivery. This implementation is not qualified by these fixtures; source freezing and native comparison are root-owned later steps.

Inputs remain original strict predictor dictionaries, explicit original profile/gallery/provider and the actual source_started.source_epoch_monotonic_sec. The origin binds once before predictor admission. Unknown/reference fields are rejected; no timing sidecars enter scheduler input. Successful queue insertion stamps availability after lock/capacity checks while the queue mutex prevents premature worker access. Missing origin or observed time before source/receptive support is an error, never clamped. Failed full-queue attempts do not create admitted metadata.

Original modeled readiness is retained in the sidecar and clock trace. Immutable scheduler input available_at_sec becomes observed queue admission. Source-progress watermarks and strict ready<minimum-watermark draining remain unchanged; finite watermarks must not exceed actual source-relative time. Actual absent-lane closure for M0 may occur before origin. Infinity is passed only through the existing explicit lane-close/finalization path.

Actual tracker and naming start/finish, worker receipt, fully constructed policy-result readiness, runtime publication and consumer receipt are distinct linked events. The complete result exists at observed_policy_decision_ready_at_sec; emitted available_at_sec reflects this result-ready clock, while input_available_at_sec preserves immutable queue admission and modeled_available_at_sec remains diagnostic. Runtime publication adds its own clock. No finish timestamp is reconstructed by adding/subtracting model costs.

The actual eligible-current-caption gate uses current decision clock minus original evidence source end with the unchanged0.75second expiry. A scheduling snapshot is visible only after actual decision completion. Queued/stalled work cannot renew source evidence by delivery. Every output reports live_evidence_fresh, live_evidence_age_sec and fixed source_evidence_expiry_at_sec. The same immutable source end/expiry is re-evaluated under the actual runtime publication lock; policy-ready and publication ages/flags remain separately recorded. Publication delay can only expire the flag, never renew it. A future UI must still expire against its own actual application clock rather than treating true as permanent.

Bounded historical correction eligibility intentionally retains the immutable observed-input timeline and original numeric horizon/boundary rules. Historical annotation can be legal while live_evidence_fresh is false. It is not current speech or direction permission. Stored admitted events never change timestamps. Original first_display_time/first_known_name_time-style fields remain input-timeline history for this compatibility path; they are explicitly labelled as not policy or GUI latency. New observed_first_display_ready_at_sec, observed_first_final_ready_at_sec and observed_first_known_name_ready_at_sec record actual result readiness. Downstream latency analysis must use these plus publication/receipt/application clocks, not backdate naming to input admission.

The sidecar retains pending events, original bounded evidence history and 4096 recent diagnostic records. Its hard limit is max_pending_events + queue_capacity + 3*4096 + 128: the original heap, queued admissions, two potentially disjoint evidence histories, recent diagnostics, one active command and up to 127 commands between prunes. It fails closed when exhausted. Utterance ready-time history is bounded by the original max_utterances. All raw trace rows remain append-only; pruning only affects live metadata.

Independent source review repair: admission now holds the metadata RLock before acquiring the worker and queue locks; the stamp follows all three lock waits. The callback does not hold a worker or queue lock while acquiring metadata, and close releases its lock before joining. A deterministic acquisition-boundary fixture covers this exact contention.

Outputs carry source_epoch_monotonic_sec, application_scope and current_source_permission. The scope is CURRENT_SOURCE_EVIDENCE, HISTORICAL_ONLY or UNRESOLVED_OR_DIAGNOSTIC. Permission is temporal only: independent identity, speech, ownership and route gates still apply. Bounded retrospective corrections and retained finalization labels are historical even when their evidence is still fresh. Publication expiry can only remove current permission. Snapshot/export utterances include the immutable history-clock labels and actual observed_first_* readiness; snapshot rows always grant no current permission. These fields do not claim widget application or repair the separate presentation ownership issue.

The pre-repair source, fixture and READMEs are preserved in application/observed_policy_v1/before_independent_repair_v1. The original IMPLEMENTATION_READY.json, OWNED_SOURCE_DELTA.diff and 43-check receipt remain unchanged. New repair evidence requires root review before any source freeze or native admission.

The adapter preserves source-progress release waiting. It may expose substantial measured staleness and change attribution; no accuracy/latency improvement or C105 repair is claimed. The selected C105 sentinel, naming/handoff/finalization cases, real queue trajectories and actual GUI test are still required. Beam hooks use separate clocks and are not adapted.

## PowerShell fixture

```powershell
$R7 = 'C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S7/20260917T141700Z'
$Py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $Py -B "$R7/application/observed_policy_v1/test_observed_policy_v1.py" --output "$R7/application/observed_policy_v1/source_checks_manual_01"
```

## Anaconda Prompt / CMD fixture

No environment installation or activation is necessary; use the existing absolute interpreter.

```bat
set "R7=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%R7%\application\observed_policy_v1\test_observed_policy_v1.py" --output "%R7%\application\observed_policy_v1\source_checks_manual_01"
```

The fixture reads original profile metadata, imports policy code and uses explicit synthetic tracker/resolver functions with bounded real worker threads. No model is loaded or inferred, no audio is read and no runtime/native session starts. It writes only a source-bound SOURCE_CHECKS.json in a fresh requested directory. Do not overwrite any prior receipt. Native use must later bind this epoch and an explicit job.s7_settings availability_clock:"observed" through the reviewed native worker; do not launch this mutable candidate directly.

