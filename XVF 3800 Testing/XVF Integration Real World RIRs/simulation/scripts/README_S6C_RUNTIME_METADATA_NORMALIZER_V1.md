# Runtime metadata normalizer V1

Purpose: produce the source-bound paced, continuous and physical metadata rows consumed by the final disposition assembler. This is a finite metadata join, not a scorer, runtime launcher, model process, candidate selector or final study certification. The six supported families are canonical paired pacing, arrival sentinel, cross-route pacing, historical B00/B01/B36 pacing, C continuous and B36 continuous.

This helper is initially held for source review. Checks use tiny in-memory fixtures only. Actual normalization requires root's explicit closed-run input scope and no active or retained PACED_QUIET_OWNER.json.

## Inputs and source authority

The helper pins the reviewed unified fast-analysis adapter, V7 inventory API and final disposition assembler. It reads the exact completed original post-analysis receipt, its original PLAN and the bound fast-analysis REQUEST. The latter must match the requested family, historical generation, runtime manifest/index or C-long admissions, and exact observer index. Original analysis sources must still match. It does not rerun original scientific conversion, logical parity or any score.

V7 admits the actual native and observer chain. Canonical/sentinel/cross must have the exact completed native grid. Historical baseline and research are separate requests with their own completed analysis; B00 retains its original S6A branch. C-long requires actual outer invocation ADMISSION bindings, not a prepared composition or manifest alone. B36-long uses its separate historical continuous chain.

The working registration receipt is pinned to the reviewed working disposition snapshot. Its bound route-settings JSON supplies the C registered fingerprints. Each C job's exact profile, cues, gallery condition, tier and whole registration row must match. The executable condition digest uses the existing working helper's formula: profile without profile_id plus cue_condition, gallery_condition and enrollment_tier. Historical original_registration_row_sha256 remains the assembler's registration key; that old CSV is descriptive and does not itself contain the executable profile. The normalized historical condition additionally binds the actual job profile digest and generation; V7 independently admits the exact original worker/profile/assets.

Optional physical rows come only from explicit V7 inventory physical IDs. The bound PHYSICAL_EXECUTIONS JSON supplies the attempt, status, owner and native session identity. Current-at-inventory owner observations supply nullable closure. Failed V1 protection outcomes stay failed physical evidence even when an original native session completed. A prepared source or duplicated score/index reference never creates an attempt. No physical totals are inferred from scored cells.

## Exact specification

All binding objects are absolute path, bytes, sha256. Replace placeholders with reviewed real completed bindings. Use a fresh input_id for every explicit source scope.

~~~json
{
  "schema": "s6c-runtime-normalization-inputs.v1",
  "status": "EXPLICIT_FINITE_SCOPE",
  "observer_index": {"path": "ABSOLUTE_OBSERVER_INDEX.json", "bytes": 123, "sha256": "EXACT_SHA"},
  "working_registration": {"path": "ABSOLUTE_WORKING_RECEIPT.json", "bytes": 123, "sha256": "EXACT_SHA"},
  "requests": [
    {
      "input_id": "one_canonical_batch",
      "kind": "canonical",
      "manifest": {"path": "ABSOLUTE_RUNTIME_MANIFEST.json", "bytes": 123, "sha256": "EXACT_SHA"},
      "paced_index": {"path": "ABSOLUTE_PACED_INDEX.json", "bytes": 123, "sha256": "EXACT_SHA"},
      "analysis_receipt": {"path": "ABSOLUTE_COMPLETED_ANALYSIS_RESULT.json", "bytes": 123, "sha256": "EXACT_SHA"}
    }
  ],
  "physical_inventories": []
}
~~~

Mode-specific fields:

| kind | Runtime inputs | Original analysis receipt |
|---|---|---|
| canonical / sentinel / cross | manifest and paced_index | Completed original RESULT with all cell_measurements |
| historical | manifest and generation=baseline or research | Completed original RESULT with selected-generation measurements |
| long_c | admissions list of exact actual outer ADMISSION bindings | Completed original ANALYSIS_RECEIPT with session result bindings |
| long_b36 | manifest; omit generation | Completed original B36 diagnostic RESULT |

Do not include mode-irrelevant inputs. There is no implicit path discovery of additional analysis scopes or automatic final-source selection. The common observer index is explicitly attached to every metadata reader.

An optional physical_inventories item is:

~~~json
{
  "input_id": "explicit_closed_inventory_subset",
  "inventory": {"path": "ABSOLUTE_V7_EXECUTION_INVENTORY.json", "bytes": 123, "sha256": "EXACT_SHA"},
  "physical_ids": ["EXACT_DURABLE_PHYSICAL_ID"]
}
~~~

Overlapping runtime requests are also rejected by actual native-result path, native-result hash and native session directory. Thus C-long admission lists [A] and [A,B] cannot count session A twice; separate physical repetitions retain their distinct native identities.

Specify distinct physical IDs. The helper refuses duplicate physical selections across inventories. Keep the original inventory's incomplete-accounting flags and timestamp when interpreting the projection. Normalization does not repair an incomplete whole-study census.

## Outputs and field meanings

A fresh REPORT/runtime_normalization/NAME contains:

- RUNTIME_ROWS.json: typed paced/long rows with candidate, taps, recipe, cue/gallery/tier, actual condition fingerprints, case/repetition/job identity where present, native result binding, owner observations, source duration and completion proof bindings.
- PHYSICAL_ROWS.json: exact selected inventory attempts including failed or unknown rows; nullable alive/creation metadata, original status, native completion distinction and authority bindings.
- RESULT.json: source specification, every output binding, metadata source snapshots, original registration sources, unresolved runtime count and whole_study_complete=false.
- FAILURE.json if a source/admission error occurs. Existing namespaces and artifacts are preserved.

The final assembler can use RESULT as a root resource and its bound RUNTIME_ROWS or PHYSICAL_ROWS as children. Select rows by input_id, candidate_id, taps and the declared scope; retain all repetitions within the actual main paced authority. No evidence_id, scientific disposition or operating-preset choice is invented here.

tail_complete means **admitted full-source journal/sample/cursor completion only**. It does not mean correct first/last words, intact phonetic onset/offset, or an acoustic clipping diagnosis.

- C rows also require exact paired final sample totals, successful finalizer/closed handles, no retained model lease or live lanes, terminal cursor and drained scheduler. Those scalar finalization proofs are retained explicitly. No separate discrete dispatch coverage certificate is invented; detailed dispatch observations stay in the bound original analysis.
- B01/B36 additionally require the original full-source research dispatch coverage and drained scheduler.
- B00 has exact complete PCM journal and terminal ASR-cursor proof, but research dispatch/drain instrumentation is unavailable. Its dispatch_tail_proof is null and drain_available is false. B00 remains a historical comparator, not a prospective operating preset.
- A missing finalization_error field is missing evidence, not an implicit null error. Missing required proof gives null tail_complete or owner_closed and PENDING_OR_UNVERIFIED, not a fabricated false/zero or successful completion.
- continuous=true is produced only through admitted actual C-long/B36-long chains and completed original continuous diagnostics. A canonical case is never relabeled continuous.

Owners_closed refers to the exact recorded PID/creation identities checked by admitted APIs, not exhaustive operating-system descendant discovery. Physical-row alive is specifically as recorded at the inventory's timestamp. Sampled resource observations and their missingness remain in original diagnostics; no continuous maxima, backlog interpolation, CM5 or hardware claim is added.

The wrapper reads bounded JSON/CSV/code metadata. Original completed cell/session analysis records may retain nested observation projections; these are matched by source/native identity without recalculating their scientific metrics. Raw event JSONL, process trajectories, audio, models, vectors and prediction bodies are not opened. Existing native payload hashes remain transitive declarations. V7 may read the registered execution manifest and closed finalization/summary JSON needed by its existing admission.

## PowerShell

Use the existing EDGE interpreter; no installation or model download.

~~~powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$helper = "$sim\scripts\s6c_runtime_metadata_normalizer_v1.py"
& $python -B $helper checks
~~~

Only after root authorizes the explicit closed-run specification:

~~~powershell
$spec = 'ABSOLUTE_REVIEWED_NORMALIZATION_SPEC.json'
$specSha = 'EXACT_SPEC_SHA256'
& $python -B $helper run --spec $spec --spec-sha256 $specSha --namespace final_runtime_metadata_NEW
~~~

The specification SHA can be inspected without running normalization:

~~~powershell
Get-FileHash -Algorithm SHA256 -LiteralPath $spec
~~~

## Anaconda Prompt / CMD

Use the exact executable directly; activation is unnecessary.

~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_runtime_metadata_normalizer_v1.py checks
~~~

After explicit authorization, replace both placeholders:

~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_runtime_metadata_normalizer_v1.py run --spec "ABSOLUTE_REVIEWED_NORMALIZATION_SPEC.json" --spec-sha256 EXACT_SPEC_SHA256 --namespace final_runtime_metadata_NEW
~~~

Successful metadata normalization is not a final operating decision. The final disposition assembler still requires exact paced plus 30Ã¢â‚¬â€œ60-minute continuous evidence for each retained operating condition; root owns that selection and whole-study acceptance.

