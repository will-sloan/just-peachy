# Actual C06540 paced review

Purpose: independently reconcile the first completed canonical C065 fast_v2 batch against its exact post-analysis outputs. `s6c_review_c065_paced_actual_v1.py` uses held inventory V7 to admit actual manifest/index/COMPLETE/CELL/native/owner/observer chains, then reads only the 40 compact measurement JSONs and two repetition indices. It checks route/grid, repeated-scene separation, one bundle/session per cell, none-mode gallery events, no-gallery naming counts/censoring, logical-parity counts, terminal scheduler/source observations, sample missingness, nested time copies and independently calculated emitted UTC summaries.

Inputs are explicitly SHA-pinned RESULT, REQUEST and observer-index paths in the helper. All deeper inputs follow their exact bindings. The result has 40 cells: repetition1 has16 cases×2 taps; repetition2 has4 cases×2 taps. Repeats and two views are dependent. The earlier failed fast_v1 attempt is outside this batch and must remain in the eventual whole-study inventory.

Do not run during any active paced/long quiet lease. No original event/process JSONL, prediction payload, waveform, embeddings, weights or full inventory is read; no scientific conversion, policy replay, scorer or neural execution runs. Existing logical parity is checked against its exact compact/native count bindings, not independently regenerated. Native RESULT still contains inherited long-schema wording; actual CELL_RESULT authoritatively classifies these as canonical single-scene sessions with no inserted gaps.

Outputs: a fresh review directory containing exact consumed metadata snapshots, `METADATA_SOURCES.json`, and `REVIEW_RECEIPT.json`. It retains four route/repetition groups, metric-specific missingness, native/outer time distinctions, and selected largest outer-wall examples. No source or prior output is changed. Observation maxima are sampled, not guaranteed peaks. EOF drain remains unavailable; emitted UTC relative to nominal playback is not GUI, phonetic or CM5 latency. Forty none-mode admission events mean zero loaded gallery profiles, not zero events. No-gallery absence of known names is a control result, not recognition accuracy.

PowerShell:

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B s6c_review_c065_paced_actual_v1.py --output "$simRoot\reports\S6C\20260910T123540Z\independent_review\c065_actual_paced_component_v3"
```

Anaconda Prompt or Windows CMD (use the exact existing EDGE interpreter; no environment installation needed):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_review_c065_paced_actual_v1.py --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\independent_review\c065_actual_paced_component_v3"
```

After execution, preserve that directory. An independently authorized reproduction must use a new output path; no unrelated fixtures or source checks need repeating. Partial review directories remain evidence if an assertion fails.

Review-only development corrections are preserved in the v1/v2 review directories: independent datetime subtraction allows0.5microsecond representation tolerance versus original epoch-float arithmetic; relevant naming clocks remain separate from two retained approximately1ms full-log reversals. No production source/result changed.
