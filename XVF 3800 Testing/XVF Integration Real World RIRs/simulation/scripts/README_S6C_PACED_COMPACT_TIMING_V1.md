# Compact actual paced timing and emission observations

Purpose: project all596 completed paced analysis cells into compact per-cell JSON, grouped JSON and a readable timing table. Inputs are bound scientific analysis results and normalized runtime results; no raw audio, models, event journals, vectors, policy replay or scorers run. The report does not select operating presets or declare S6C complete. Source checks share this README.

Input spec schema s6c-paced-compact-timing-inputs.v1, status EXPLICIT_COMPLETE596_INPUTS, expected_cells596, and exactly16 inputs. Each input has input_id, cohort (main/cadence_gate/arrival/cross), analysis binding and normalization binding, each path/bytes/SHA256. Main13 candidates×40=520, cadence24, arrival12, cross40. The same controls normalization result may support separate B00/B01 analysis generations; exact native/job joins still prevent duplicate actual results. Every read is source-bound and confined to the report folder, max32MiB/file. No file tree enumeration.

Exact input/cohort/candidate/ASR tap/identity tap/condition hash/repetition remain separate. Group rows retain the complete normalized condition. Each normalized row must contain the exact consumed analysis RESULT and measurement path/bytes/SHA256 in its proof_bindings. Canonical measurement taps must agree with normalized ASR/identity taps; historical tap admission remains in its original bound normalizer. Native session directory is retained. A repeated canonical native-result path, SHA256 content identity, or actual session directory is rejected independently, including a copied result at a different path. Distinct physical repetitions remain separate. Mismatched job/case/repetition/native bindings, incomplete analysis, occupied namespace or wrong cohort totals cause rejection. Native source/owner/tail/parity values remain explicit. Repetitions and overlapping diagnostic cohorts are not independent scenes.

Metrics: aware UTC source_started→session_completed interval and its ratio to source duration; separate original canonical outer/native/startup and historical worker/admission/loading values; sampled RSS/USS/Windows-private-commit peaks and sampling gaps; original event UTC emission-minus-source-cursor distributions; actual naming turns grouped by roster/reference/attainability and each original delay/censoring status. Missing and unavailable values remain null, never0. The ratio is not pure algorithm RTF or acoustic/GUI latency. Partial event lag does not measure partial-text accuracy. Observer peaks are maximized, not added; sampled RSS sums can double-count shared pages. UTC reversals are preserved as counts, not silently repaired. Linear-interpolated percentiles are descriptive and have no confidence-interval claim.

Observation denominators: grouped scalar metric observed/missing counts refer to cells with finite/null values. In particular, a resource-peak observed count is the number of cells with an available peak, not the number of process samples. Event lag counts refer to original emission records of that event type. Name-delay counts refer to original turn occurrences within the exact roster/reference/attainability and original censoring-status bin. They are not interchangeable with cells, unique people, or independent scenes.

Per-cell observation_counts preserves available original trajectory sample totals, null-LIVE/missing-telemetry/incomplete-tree counts, measured phase sample count, and observed/missing counts by original process, telemetry, backlog and external-process metric key. Unavailable fields stay null (or an empty metric map where no original series exists); they are never inferred to be zero. Trajectory and external observer series can overlap and their counts are never added or deduplicated. Sample maxima remain observed-sample maxima, not continuous whole-run bounds. Original sampler tree flags do not independently establish complete OS descendant enumeration. Grouping does not impute missing observations or discard UTC reversals; original name-clock validity remains visible.

Outputs in reports/S6C/20260910T123540Z/paced_compact_timing/NAMESPACE: CELL_SUMMARIES.json, GROUP_SUMMARIES.json, PACED_TIMING_OBSERVATIONS.md and source-bound RESULT.json. The receipt records denominator_definitions; cell rows retain analysis/measurement/native bindings and native_session_dir. Raw evidence remains local. Use a fresh namespace for a justified new run; no overwrite or implicit resume. The exact actual spec/commands will be in the execution folder.

PowerShell:
~~~powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B s6c_paced_compact_timing_v1.py checks
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B s6c_paced_compact_timing_v1.py run --spec 'ABSOLUTE_SPEC.json' --spec-sha256 EXACT_SPEC_SHA256 --namespace full596_v1
~~~

Anaconda Prompt / CMD:
~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_paced_compact_timing_v1.py checks
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_paced_compact_timing_v1.py run --spec "ABSOLUTE_SPEC.json" --spec-sha256 EXACT_SPEC_SHA256 --namespace full596_v1
~~~

Run after all original analysis/normalization outputs close and before a quiet native interval. Focused checks cover missing denominators, nonfinite input, UTC offsets/reversals, maxima, group boundaries, exact normalized proof membership, canonical tap joins, independent path/hash/session duplicate rejection, distinct repetitions, and available versus unavailable resource sample counts. Independent review additionally checks the actual per-cell schemas. Shared original scientific code and source receipts remain unmodified.

The pre-repair helper/README and reproduced original 14 checks are preserved under simulation/staging/s6c/20260910T123540Z/timing_projector/before_join_repair_v1. The provenance/count repair does not change scientific event/name arithmetic or original source results. Run checks with the commands above; the repaired bound check receipt is reports/S6C/20260910T123540Z/paced_compact_timing/source_checks_v2/SOURCE_CHECKS.json. These checks do not execute the 596-cell projection.
