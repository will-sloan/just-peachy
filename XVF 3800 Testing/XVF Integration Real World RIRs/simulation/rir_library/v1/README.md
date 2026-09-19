# Canonical four-channel RIR library v1

This is the current authoritative 121-record library, defined by RIR_MANIFEST.json. EXTRACTED: 95; EXTRACTED_WITH_LIMITATIONS: 26; FAILED: 0. Historical S1 WAVs are not this library. Each successful ID has exactly wav/<run_id>_rir.wav: 16 kHz, FLOAT32, MIC0 MIC1 MIC2 MIC3. No peak normalization or mono exports.

Read RESULTS.md for outcomes and limitations, RIR_SUMMARY.csv for one row per ID, and EXTRACTION_CONFIG.json for the exact frozen method. The manifest includes original statuses, source hashes, both 1.00 m corrections, effective distances ≤5 m, signed angles with ±5° user uncertainty, room context, unknown geometry and all exclusions.

## Intended use and scaling

Convolving a 16 kHz mono numerical **post-software-gain drive** with all four RIR columns predicts Category 3 recorded normalized full-scale signals within the declared band/tail. Preserve the four columns and relative output scales across records. Never peak-normalize RIRs, divide out gain 10, apply SYS_DELAY −32 again, infer calibrated SPL or substitute exact label-derived delays. A 50 ms common pre-onset convention replaces inseparable bulk latency; this is not absolute sound travel time.

Nominal pass region: 110–7000 Hz; smooth transitions 80–110 and 7000–7300 Hz. Actual supported intervals and clock/tail limitations are per-record metadata. A stored duration is not RT60. can_proceed_to_hil_proof means usable as an input to a future proof; physical_replay_validated and simulation_ready remain false. Later replay must establish the appropriate unity/zero or other documented replay-domain contract rather than applying acquisition gain/delay a second time.

## Inputs, environment and commands

Original captures remain in their hash-bound local locations; the ZIP does not contain them. Existing C:\Users\amiri\anaconda3\python.exe supplies NumPy, SciPy, soundfile, matplotlib and psutil. No package installation, GPU, hardware access or H2 changes are needed.

PowerShell — verify/resume this exact report/library pair:

```powershell
$s2Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s2Report = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S2\20260908T203309Z'
$s2Library = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\rir_library\v1'
$s2Python = 'C:\Users\amiri\anaconda3\python.exe'
& $s2Python "$s2Sim\scripts\s2_run.py" --report $s2Report --library $s2Library --workers 4
```

Anaconda Prompt / Command Prompt:

```bat
set "S2SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S2REPORT=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S2\20260908T203309Z"
set "S2LIBRARY=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\rir_library\v1"
set "S2PYTHON=C:\Users\amiri\anaconda3\python.exe"
"%S2PYTHON%" "%S2SIM%\scripts\s2_run.py" --report "%S2REPORT%" --library "%S2LIBRARY%" --workers 4
```

The completed run should resume all successful IDs without new WAVs. Do not reuse this report with a different library path. Keep one coordinator at a time. The frozen control/config/code gates must match. For different inputs/methods, use a new report and the next library version; do not overwrite this version. See simulation/S2_README.md for the initial assessment/control commands and presentation/package rebuild commands.

Files produced: canonical WAVs, RIR_MANIFEST.json, RIR_SUMMARY.csv, EXTRACTION_CONFIG.json, RESULTS.md and this README. Internal metrics, progress, binding receipts and small QC arrays reside in C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S2\20260908T203309Z; no second current RIR variant set is exported. Full original S1 evidence remains unchanged.

Validation scope: 60 final known-FIR checks, 1586 library/integrity checks, one fresh real numerical regeneration, common-channel timing/level checks and same-sweep internal reconstruction. No independent acoustic, speech/model-performance or physical/HIL validation is implied.
