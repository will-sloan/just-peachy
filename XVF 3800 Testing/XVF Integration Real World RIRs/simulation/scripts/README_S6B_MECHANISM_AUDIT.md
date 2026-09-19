# Audit actual S6B mechanism activation

`s6b_mechanism_audit.py` counts operations that the actual frozen application executed. It reads tracker lineage and checks those counts against the actual tracker snapshot. It separately reads native embedding admission and ASR endpoint records, deduplicated by neural job key. The script creates no model sessions, does not access hardware and does not use reference identities or geometry.

## Inputs, outputs and interpretation

The default epoch is the authoritative `epoch2`. The frozen manifest and its metadata are checked by the validation API. Run with the repository Python, which matches the native Python/NumPy versions. No packages need to be installed.

`self-check` executes the frozen tracker on a small deterministic input fixture and validates extraction of one actual N01 quarantine/recovery and one N03 escrow release. It also checks the native endpoint-event schema, distinguishing advisory-only/coincident resets and rejecting a missing full-dispatch event. `mechanisms/EXTRACTOR_CHECKS_V2.json` is a code check, not an empirical performance result. The earlier fixture is preserved.

`pilot` consumes `epoch2/PILOT_NEURAL_INDEX.json`. It runs the actual canonical neural profile's tracker on its exact cached observations, then audits the tracker and its original native admission/endpoint log. The output is `mechanisms/PILOT_MECHANISM_AUDIT.json`. Canonical neural profiles are not the forty comparison methods, so a mechanism disabled in those profiles must not be called unsuccessful on that basis.

`predictions --index PATH` consumes an explicitly selected actual prediction index. It verifies prediction hashes, code/profile identity and native evidence bindings. Its default output is `mechanisms/CHALLENGE_MECHANISM_AUDIT.json`; use `--output-name NAME.json` to preserve another population separately. The report records index completeness and its exact number of outputs rather than assuming a fixed sample count.

All reports live under `simulation/reports/S6B/20260909T230840Z/mechanisms`. They include per-output details, per-profile totals, actual activation counts, native-job totals, source/code hashes and integrity violations. A violation returns FAIL and a nonzero exit. Zero observed activations are retained explicitly.

The audit covers track creation, provisional/committed decisions, independent evidence admission, prototype updates, overlapping-update suppression, capacity rejections, innovation proposals, dormancy/reentry, multiple prototypes, N01 quarantine/recovery/stale-anchor audits, N03 escrow hold/release/reject/expiry, prototype rollback and forward label revisions. It checks revision target availability and replacement-state consistency, plus declared commitment and memory bounds.

Graph path recomputation is not a structural merge. This implementation emits forward association revisions; structural track merge and split capabilities are explicitly marked absent. Tracker label revisions are separated from ongoing transcript-display changes and bounded transcript reconciliation. A retained-node cap is not an edit-count cap.

Cue reasons distinguish actual missing/stale/reordered/invalid packets, effective positive credit and valid packets whose credit was suppressed. A voice-prototype/cue contradiction is observable disagreement, not proof of a ground-truth directional error. Paired labels under a currently empty cue are descriptive: earlier cue history can have changed the tracker's state. Disabled-cue parent parity is established separately by the validation tests.

For N04, counts come from actual adviser dispatch records and reset events: proposals, acceptance, rate limits, breaker openings, advisory-only resets and resets coincident with native endpoints. The adviser does not expose every internal stale/invalid rejection reason; `no_proposal` is never relabeled as stale. For N05, debt-due opportunities are separated from admitted/rejected windows and the narrower case where debt was the sole reason to select an earlier cadence. Merely setting a flag or counting debt-due rows does not establish an additional observation.

The native upstream totals are deduplicated by actual neural job. Sharing one recipe among many downstream trackers does not multiply neural runs. Unknown fractions use decision-observation counts only, not sole-speech-time or word-error denominators. Unique evidence totals are per anonymous track and may cover overlapping source spans across different proposed tracks.

## PowerShell

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_mechanism_audit.py' self-check --epoch epoch2
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_mechanism_audit.py' pilot --epoch epoch2
```

Example for a completed actual prediction subset:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_mechanism_audit.py' predictions --epoch epoch2 --index '.\reports\S6B\20260909T230840Z\R0_CHALLENGE_PREDICTION_INDEX.json' --output-name R0_CHALLENGE_MECHANISM_AUDIT.json
```

Use the full final index path when it is complete. Do not silently treat a subset as the full campaign.

## Command Prompt or Anaconda Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_mechanism_audit.py" self-check --epoch epoch2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_mechanism_audit.py" pilot --epoch epoch2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_mechanism_audit.py" predictions --epoch epoch2 --index "reports\S6B\20260909T230840Z\R0_CHALLENGE_PREDICTION_INDEX.json" --output-name R0_CHALLENGE_MECHANISM_AUDIT.json
```

The extractor fixture and actual 64-row native pilot audit passed. That establishes the extractor on real application evidence; per-method activation and inactivity must be read from the selected main-prediction population.

The completed R0 subset is preserved separately in `R0_CHALLENGE_MECHANISM_AUDIT.json`: 2,024 predictions across 23 profiles and 88 outputs per profile, sharing 88 native jobs. `R0_CHALLENGE_MECHANISM_SUMMARY.json` is its compact packaging derivative; it retains the summary and interpretation fields, removes repeated per-job key lists, and binds the full audit by hash. Neither file represents the remaining neural recipes. Historical B00 has no S6B tracker instrumentation, so its empty counters do not establish zero activity. N04/N05 were disabled in R0 and require the later full-index audit.

## Full challenge endpoint-extractor correction

The first full `CHALLENGE_MECHANISM_AUDIT.json` is preserved as a failed audit. All 3,872 tracker rows passed, but 22 actual endpoint jobs exposed a reporting typo: the extractor selected `research_asr_dispatch_cost`, while frozen APP emits `research_asr_full_dispatch_cost`. The original executable bytes are preserved as `mechanisms/s6b_mechanism_audit_before_endpoint_fix.py`; this is historical source provenance, not a new candidate. The correction changes only the event selector and adds an explicit missing-full-dispatch guard. It does not alter native events, profiles, model calls, predictions or scores.

The final complete rehash uses the corrected extractor and a new report filename:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_mechanism_audit.py' predictions --epoch epoch2 --index '.\reports\S6B\20260909T230840Z\CHALLENGE_PREDICTION_INDEX.json' --output-name CHALLENGE_MECHANISM_AUDIT_FINAL.json
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_mechanism_audit.py" predictions --epoch epoch2 --index "reports\S6B\20260909T230840Z\CHALLENGE_PREDICTION_INDEX.json" --output-name CHALLENGE_MECHANISM_AUDIT_FINAL.json
```

Use a new output name for later repeats. `ENDPOINT_EXTRACTOR_CORRECTION.json` records the failure, source versions, targeted fixture and final audit linkage. Do not reinterpret the failed report as bad native recordings or successful absence of endpoint advice.

## Completed full R0 population

`R0_FULL_MECHANISM_AUDIT_FINAL.json` is the separate passing audit of all 11,040 full-bank R0 predictions: 23 profiles, 240 scenes and both taps, sharing 480 actual native jobs and 15,649 embedding calls. It preserves the earlier panel and full-challenge audits. `R0_FULL_MECHANISM_SUMMARY.json` and `.md` are its compact source-bound derivatives. Their exact cell-grid and independently aggregated counter checks passed. Reproduction is documented in `README_S6B_MECHANISM_SUMMARY.md` beside this file.

The larger population makes bounded-gallery failures visible: several 16-track policies rejected new associations in 127 of 480 outputs, while B36's explicit 256-track control observed at most 27 tracks. Read exact per-profile/tap capacity, cue-credit and revision counts from the compact JSON; activation counts do not establish a beneficial comparison. N04/N05 remain disabled in R0 and their evidence belongs to the separate all-recipe challenge audit.
