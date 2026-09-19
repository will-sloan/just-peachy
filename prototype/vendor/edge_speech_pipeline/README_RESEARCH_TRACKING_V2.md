# S6B bounded anonymous trackers

`research_tracking_v2.py` implements the actual opt-in application trackers used by the S6B common scheduler and deterministic replay. It does not load a model, open a microphone, read reference schedules, identify named people, or train anything. The original S6A module remains separate. `checks_research_tracking_v2.py` runs meaningful, model-free checks and optionally verifies the original common-scheduler control against all 480 previously cached ReDim outputs.

## Inputs and outputs

Create `S6BTrackingConfig(...)`, then `S6BTracker(config)`. Call:

```python
decision = tracker.update(
    embedding, source_start_sec, source_end_sec, available_at_sec,
    spatial=None, speech=True, overlap=False,
)
```

The embedding is a finite, nonzero 192-dimensional vector from the existing ReDim checkpoint. New policies normalize its float32 copy. `original_common` passes the already-normalized float32 value to the original `SpeakerTracker` unchanged, preserving its arithmetic. The source span is contiguous and 0.5–3 seconds long. Source ends and availability are nondecreasing, and the window must have arrived by its availability time. Equal ends with different starts allow a short and long view of the same arrived audio. An exactly repeated span raises an error. Speech and overlap gates are booleans produced upstream; rejected windows admit no identity evidence.

An optional delivered observation has `angle_deg` in the native folded interval [0, 180], `available_at_sec`, `reliability` in [0, 1], `valid`, and optional `sequence`, positive `energy`, `source_start_sec`/`source_end_sec`. Both packet-delivery age and source age (when measured) must qualify. Reordered or old re-delivered sequence numbers are rejected. Missing source age remains an explicitly unmeasured source-age case; delivery-age checks still apply. This module does not infer signed geometry. Angles 0 and 180 are distinct linear endpoints.

Results contain `anonymous_label`, `display_label`, `cluster_id`/`tracker_id`, `decision_id`, `first_decision_id`, `evidence_id`, `state`, `committed`, unique evidence duration, disjoint evidence count, prototype version, source/availability times, reason, and `lineage`. `decision_to_speaker()` adapts the normal result fields to the application's `SpeakerDecision`. The original control also returns the original `evidence_sec`, which counts elapsed legacy span; `unique_evidence_sec` remains separately measured. `snapshot()` returns bounded state and mechanism activation counters, without vectors or reference identities.

The caller measures tracker wall cost. This module never adds method-specific compute time to the shared upstream cached availability clock. Source availability is a modeled causal gate, not a claim of physical real-time execution.

## Executed methods

| Mode or option | Actual mechanism and limits |
|---|---|
| `original_common` | Existing anonymous `SpeakerTracker`, empty in-memory roster, original arithmetic. B36 must explicitly set `max_tracks=256` to preserve this bank's historical behavior (observed maximum: 27 clusters). A cap of 16 changed real outcomes and its failure receipt is preserved separately. Historical B0 remains a separate result. |
| `one_person`, `all_unknown` | Input-only diagnostic controls. They are marked as controls in every decision. |
| `voice` | Threshold and ambiguity-gated incremental voice association, unique-time ledger, independent-window commitment and prototype updates. |
| `angle` | Angle-dominant anonymous association among voice-compatible tracks. Severe voice conflict rejects the association even at an unchanged bearing; a new provisional voice branch can be created. Audio speech/overlap eligibility applies. It is not named-identity recognition. |
| `static` | Fixed-weight voice/location compatibility with a severe voice-conflict floor. |
| `sustained` | Location contribution admitted after an observation-cadence-aware persistence period. Current packet freshness and persistence continuity are separate conditions. |
| `decay` | Location contribution decays with the age of that track's last qualified location. |
| `adaptive` | Qualified cue quality, age, and current voice strength set the location contribution. Strong voice reduces location authority. |
| `innovation` | Leaky bearing-innovation CUSUM proposes a directional change; it does not force a new identity. |
| `folded` | Three-point bounded marginalization over bearing uncertainty in [0, 180], with a Gaussian compatibility kernel. |
| `conflict_reject` | Observable independent voice/location contradictions suppress cue authority and can quarantine the sensor credit. |
| `bayes` | A bounded beam of latent association paths, tempered emissions and stay prior; accumulated mass is an engineering hypothesis score, not a calibrated identity probability. |
| `hsmm` | Bounded latent track/duration states, observation-duration increments, minimum-duration switch penalty, and capped-duration relaxation. It cannot force an association below the voice eligibility threshold. |
| `global_assignment` | Bounded beam assignment of recent acoustic microgroups with soft pairwise acoustic consistency and continuity costs. Sequential groups may reuse the same identity. The serial mono stream provides no independent simultaneous observations, and no one-to-one occupancy constraint is imposed. This is approximate joint assignment, not an exact Hungarian solver. |
| `dual_memory` | Slow voice prototype updates, faster qualified location updates, dormant tracks, and stricter voice evidence for reentry. |
| `multiprototype` | Up to three bounded voice prototypes per track by default; disjoint sufficiently similar novel views can add a slot. |
| `quarantine` | Saves a prototype checkpoint before an independent update. Later disjoint audio that clearly prefers the checkpoint restores it and proposes a forward Unknown revision for the quarantined update. A rollback is observable conflict handling, not proof that the prior label was wrong. |
| `delay_graph` | Recomputes a bounded arrived-evidence Viterbi path. High-confidence reconciliation emits forward revisions within a fixed time horizon. |
| `sensor_quarantine_enabled` (N01) | Counts disjoint, clean observable contradictions. Each contradictory packet immediately loses authority, so it cannot overwrite the memory used by the next audit. Repeated contradictions set sensor credit to zero. Credit recovers only after a hold and multiple disjoint later voice/location agreements. If all remembered locations age out, bounded retained anchors may audit recovery but receive no association credit during probation. |
| `update_escrow_enabled` (N03) | A cue-assisted prototype update waits in one per-track escrow slot. A later disjoint agreeing vector releases it; disagreement or expiry discards it. Missing/disabled cues bypass escrow, preserving the matched voice parent. |

For a spatial-only mode, `cues_enabled=False` executes the exact same voice-parent code path, including operational decisions and lineage. Optional N01/N03 flags are also bypassed when cues are disabled. Structural modes such as Bayesian, dual-memory and HSMM keep their structural parent with cues disabled. Enabled but missing cues leave the angle diagnostic Unknown; it should not be interpreted as a voice method.

Except for the angle-dominant diagnostic's severe-conflict floor, location terms operate only among tracks that already pass the voice association threshold. Thus the normal spatial variants can change association ordering/ambiguity, but cannot rescue a voice match below that threshold. Wrong stable and same-bearing cues are tested explicitly.

`config.field_usage()` lists active fields, inactive defaults and any nondefault inactive numeric fields. Registration should reject or explicitly account for `nondefault_inactive_fields`. A field being reachable is not evidence that the actual dataset exercised it: use `snapshot()['operations']` and decision lineage for observed activation counts. A synthetic activation check never establishes an empirical improvement.

## Evidence, revision and resource rules

One one-second window does not automatically commit a new track: the defaults require at least one unique second **and two disjoint windows**. Overlapping windows contribute only newly covered seconds and cannot update a prototype independently. Silence gaps do not count as unique speech evidence. The greedy disjoint count is conservative; it does not claim statistical independence of adjacent speech. A provisional label can be displayed immediately while commitment remains false.

Each returned first decision remains unchanged. A revision appears in a later decision's lineage as `event='label_revision'`, with `revision_of` pointing to the earlier decision, the earlier evidence ID, old/replacement track IDs and label, original and current availability, and a reason. The current node's `latest_track` is separate from its immutable `first_track`. Downstream transcript routing must record first and latest labels separately; a tracker proposal is not itself a rewritten transcript. Revisions do not retroactively move unique evidence or rewrite prototype history.

Revision events also specify `replacement_state` and `replacement_committed`; an Unknown rollback therefore cannot inherit the committed state of its triggering decision. `max_revision_records` bounds retained tracker nodes, **not edits per node**. The scheduler separately limits bounded forward reconciliation per utterance with `max_revisions_per_utterance`. Ongoing ASR-display label changes and bounded reconciliation have separate meanings and counters; a history limit must not be reported as an edit-count limit.

Defaults bound tracks at 16, prototypes at 3, revision records at 32, graph nodes at 8, hypotheses at 8 with path horizon 8, HSMM duration bins at 8, global groups at 4 and assignment beam width at 16. The ledger collapses old non-overlapping intervals into a scalar. Exact duplicate detection stores only 256 recent spans; older duplicates cannot pass the nondecreasing source-end check. Track-cap saturation returns Unknown instead of silently recycling an identity. No files or truth objects enter the predictor.

## Run the focused checks

Use the installed Python with NumPy; no package installation or model download is needed. The following commands use the verified local Anaconda Python. The working directory must be `Evaluation Tool`, so the package imports resolve.

**PowerShell:**

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& 'C:\Users\amiri\anaconda3\python.exe' -m app.edge_speech_pipeline.checks_research_tracking_v2
```

**Command Prompt or Anaconda Prompt:**

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\anaconda3\python.exe" -m app.edge_speech_pipeline.checks_research_tracking_v2
```

The checks cover every mode, disabled-cue exact parity, first-window commitment, unique/disjoint evidence, source-clock errors, delivered/source freshness, dropped/reordered cues, metadata renaming and future-prefix invariance, sensor quarantine/recovery, escrow release, bounded temporal/assignment states, actual prototype rollback and graph revision, and input-only diagnostic controls. The default command prints results and exits nonzero on failure; it writes no report.

## Recheck all 480 cached outputs without inference

The optional `--feature-index` reads the completed S6A JSON index and its already-generated JSON/NPZ files (the NPZ files are on G:). It verifies each indexed file hash, feeds the identical arrived vectors to the original app tracker and `original_common`, compares every `SpeakerDecision` field, and separately checks the historical native anonymous labels. These labels are used only by the checker, after prediction. `--output` creates the requested JSON receipt with code hashes, test result, population and parity counts.

**PowerShell:**

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& 'C:\Users\amiri\anaconda3\python.exe' -m app.edge_speech_pipeline.checks_research_tracking_v2 --feature-index 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6A\20260909T202250Z\cues\FEATURE_INDEX.json' --output 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z\tracking\TRACKER_CHECKS.json'
```

**Command Prompt or Anaconda Prompt:**

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\anaconda3\python.exe" -m app.edge_speech_pipeline.checks_research_tracking_v2 --feature-index "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6A\20260909T202250Z\cues\FEATURE_INDEX.json" --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z\tracking\TRACKER_CHECKS.json"
```

The final completed run passed 24 focused tests and full parity for 480 outputs / 15,649 actual cached vectors with zero mismatches at the explicit B36 cap of 256. The observed historical maximum was 27 clusters. `ORIGINAL_COMMON_CAP16_FAILURE.json` preserves the rejected cap-16 check with 1,412 field mismatches; it is an unranked control-configuration failure, not a method result. The final receipt binds the exact module/check hashes and current test count. Rerun after any policy change before freezing the common replay. This is functional and arithmetic verification; main-method results, costs and output quality must come from the actual S6B comparison.
