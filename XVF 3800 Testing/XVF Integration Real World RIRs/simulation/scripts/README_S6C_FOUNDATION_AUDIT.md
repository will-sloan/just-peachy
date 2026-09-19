# S6C foundation: original voice-gate controls and genuine trace opportunities

This script reproduces the six supplied idealized controls against the unchanged S6B epoch2 tracker, demonstrates the retired-versus-stored capacity edge by an explicit state intervention, and observes the original selector while replaying existing native vectors. It does not alter the application, S6B source, model weights, old results, enrollment profiles, recordings or hardware. It runs no neural model.

The default scope is B09/B10, B16/B17 and B24/B25 across all 240 canonical scenes and both taps: 2,880 existing prediction cells. A bounded smoke can select the first two canonical case IDs; that is implementation validation, not an accuracy panel. These six profiles cover dual memory, fixed long-evidence voice/adaptive tracking and event-cadence voice/adaptive tracking. No inference about unselected profiles is made.

## Inputs

- Sealed S6B LOCAL_ARTIFACT_INDEX.json (the expected SHA256 is pinned in the script), FULL_PREDICTION_INDEX.json and epoch2/FULL_ALL_NEURAL_INDEX.json.
- The exact frozen epoch2 application under simulation/staging/s6b/20260909T230840Z/epoch2/app.
- Supplied S6C diagnostics/check_voice_gate_interaction.py, expected receipt, and packaged tracker.
- Selected existing prediction JSON files, their hash-bound native run receipts/vector arrays, and exact delivered cue traces. The script reads no waveform, neural model or evaluator speaker truth.

The native evidence JSON remains transitively bound by the native receipt and prediction identity. Its large segmentation/ASR data is not read again. Features used in this audit are taken from the exact admitted prediction; vectors from the matching admitted native receipt. Their counts, source spans, actual decision times and complete regenerated decisions are checked. Source/cue parameters are never reconstructed from ground truth.

## Outputs

Everything is created beneath the new S6C report namespace. Existing output directories are refused.

- provided_controls/: byte-identical copies of the supplied script and original tracker, and the newly generated control receipt. The supplied pack stays unchanged.
- SOURCE_CONTROL_RESULTS.json: six exact case matches, the explicit retirement fixture, and static absence of retirement assignments.
- PER_CELL_DECISION_OPPORTUNITIES.csv: all selected scene/tap/profile rows, exact parity and lifecycle/opportunity counters.
- PROFILE_TAP_PREVALENCE.csv: separate O0/O1 numerators, denominators and affected-cell counts.
- MATCHED_PARENT_TRACE_COMPARISON.csv: actual internal action/support/word and latest-label sequence differences for the three requested pairs.
- REPRESENTATIVE_DECISION_EXCERPTS.json: bounded local examples with scalar candidate scores and source identities; no vector values or correctness labels.
- SOURCE_TRACE_BINDINGS.json: full local provenance for selected predictions, native vector receipts and cues.
- TRACE_AUDIT_RECEIPT.json and FOUNDATION_AUDIT_RECEIPT.json: coverage, source/code/README hashes, exact original-decision and final-state parity.
- FAILURE.json and an optional precise parity-failure excerpt if a bound input or comparison fails. No failed row is silently accepted.

## Run in PowerShell

Use the already working EDGE interpreter. No environment installation or activation is required.

~~~powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
& $py "$sim\scripts\s6c_foundation_audit.py" --mode all --limit-cases 2 --output "$sim\reports\S6C\20260910T123540Z\foundation\smoke_v1"
& $py "$sim\scripts\s6c_foundation_audit.py" --mode all --output "$sim\reports\S6C\20260910T123540Z\foundation\audit_v1"
~~~

## Run in Anaconda Prompt or Command Prompt

~~~bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
"%S6C_PY%" "%SIM%\scripts\s6c_foundation_audit.py" --mode all --limit-cases 2 --output "%SIM%\reports\S6C\20260910T123540Z\foundation\smoke_v1"
"%S6C_PY%" "%SIM%\scripts\s6c_foundation_audit.py" --mode all --output "%SIM%\reports\S6C\20260910T123540Z\foundation\audit_v1"
~~~

Run only one audit worker. Use a new output suffix for an intentional rerun; do not overwrite earlier failed or successful evidence. --mode controls runs only the six supplied controls and lifecycle fixture; --mode traces runs only the selected trace audit. --profiles B09 B10 selects a complete paired subset. The script rejects duplicate/unsupported profile IDs. --limit-cases is 1–240, deterministic lexical case order. Without it, all 240 are required.

## Interpretation and invariants

The observer subclasses only _select, captures its current candidate scores without mutating inputs/state, and calls the unchanged original selector exactly once. It feeds the original native vectors, support, speech/overlap flags and recorded modeled availability directly to the same tracker update used by the original scheduler. Every entire regenerated decision dictionary and final tracker snapshot must equal the preserved prediction exactly. This bypasses ASR/display scheduling only for targeted tracker inspection; it does not validate a new runtime integration or regenerate transcript attribution.

A combined-score crossing of the numerical cosine gate is descriptive. S6B never declared that an uncalibrated combined score shares the cosine threshold. The fixed 0.05 borderline band is a prospective audit bin, not a calibrated operating threshold. A local voice-only action comparison holds the current cue-influenced state fixed; it is not an end-to-end cue-off counterfactual.

The six supplied cases are constructed mathematical reachability controls, not six empirical speech errors. The manually retired record is likewise a state fixture. Static source inspection shows no automatic retirement writer in this S6B tracker; dormant does not mean retired. Actual bank retirement prevalence is separately observed, never inferred from that fixture.

Track counts are software hypotheses. NumPy prototype bytes exclude Python containers, history, models and all other process memory. Capacity-hit span sums overlap; the separate union counts unique blocked source-time support. Repeated decision opportunities and two correlated taps are not independent people or conversations.

B09/B10 and B16/B17 have matched native support; compare their exact internal actions even if aggregate cpWER matches. B24/B25 changes cue-driven embedding admission as well as tracking, so unmatched spans and the bundled comparison remain explicit. No word accuracy, identity correctness, angular calibration, acoustic error prevalence or CM5 qualification is inferred here.

