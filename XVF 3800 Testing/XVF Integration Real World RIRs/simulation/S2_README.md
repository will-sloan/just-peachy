# Complete 121-record RIR library

The full library is complete: **95 EXTRACTED, 26 EXTRACTED_WITH_LIMITATIONS, zero FAILED**. The authoritative deliverable is [rir_library/v1](rir_library/v1/README.md), with exactly 121 four-channel 16 kHz FLOAT32 WAVs and all IDs in RIR_MANIFEST.json. Historical S0/S1 files and original captures remain untouched. Six exact Loeb Caf and 52 historical exclusions remain excluded; Upper Loeb remains active.

Environment: existing C:\Users\amiri\anaconda3\python.exe, NumPy/SciPy/soundfile/matplotlib/psutil already installed. CPU only, four workers and one inner numerical thread. No installation or hardware/H2 access.

scripts/s2_assess.py reads bound S1 parent/selected inputs, the exact archived source and existing known-FIR fixture generator. It writes a single pilot edge assessment, zero/±10 ppm clock controls, parent receipts and scope/resource snapshots to a new S2 report directory. It never publishes alternate RIRs or rewrites S1.

Initial PowerShell command:

```powershell
$s2Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s2Report = Join-Path $s2Sim 'reports\S2\20260908T203309Z'
& 'C:\Users\amiri\anaconda3\python.exe' "$s2Sim\scripts\s2_assess.py" --report $s2Report
```

Anaconda Prompt / Command Prompt:

```bat
set "S2SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S2REPORT=%S2SIM%\reports\S2\20260908T203309Z"
"C:\Users\amiri\anaconda3\python.exe" "%S2SIM%\scripts\s2_assess.py" --report "%S2REPORT%"
```

The assessment refuses to replace an existing result. The initial commands above are execution documentation; do not rerun them on this completed report. Hardware replay and real-world validation remain later work.

## Final policy and evidence

One nominal 110–7000 Hz pass region, with raised-cosine transitions 80–110 and 7000–7300 Hz, preserves more supported spectrum than S1. Source-only ridge attenuation never boosts weak source bins. The symmetric 2049-tap FIR is common across MIC0–MIC3. Per-record supported intervals remain separate from the chosen filter.

Per-record marker regression uses fractional-position waveform comparison for its coherence diagnostic. The integer-sample comparison falsely reduced ±10 ppm fixture coherence; corrected controls recover the expected clock without treating early-energy concentration as a mandatory gate. No microphone channel is independently warped/aligned. Selected policies: 102 per-record marker corrections, ten zero-compatible intervals, nine conservative zero fallbacks with sensitivity evidence.

All 60 final known-FIR checks passed, including expanded-band gain and cross-record scaling. One full-reference FFT-length bug was caught and fixed before freeze; its failed evidence remains recorded. The final library passed 1,586 format/identity/hash/relative-timing/regeneration checks. Canonical WAVs total about 21 MiB; processing all 121 took 204.36 seconds.

Read rir_library/v1/RESULTS.md for limitations. There are 120 inputs suitable to proceed to a later HIL proof within their limits. JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R13 (low table, Opening Behind Listener, flat, −165°, 2.85 m) has material clock-sensitive spatial uncertainty and is retained for limited offline use. Physical replay and independent acoustic validation remain unperformed for every record.

## Script purpose, inputs and outputs

| Script | Contract |
| --- | --- |
| s2_assess.py | Bound S1 parents and pilot/source -> one edge assessment, small clock controls, scope/resource receipts. Does not publish RIR variants. |
| s2_signal.py | Imported signal functions. Four-channel recording/reference -> shared timing, bounded ESS weighting, one candidate and numerical metrics. No file writes or hardware. |
| s2_controls.py | Existing known-FIR generator and draft policy -> seven fixtures/60 checks and frozen EXTRACTION_CONFIG.json if all pass. Refuses to rewrite an already frozen config. |
| s2_code_gate.py | Passed controls and frozen config -> numerical source-hash gate. Rejects code newer than controls or a changed existing gate. |
| s2_run.py | Exactly 121 active IDs, bound consumed inputs and frozen gates -> one canonical WAV per success, per-record receipts, small QC arrays and resource/heartbeat logs. Four workers; one writer. |
| s2_plots.py | Saved metrics, QC arrays and canonical WAVs -> two aggregate PNGs plus a few noteworthy-case plots. No original-capture processing. |
| s2_finalize.py build | Complete per-record receipts/WAVs -> full identity/format/hash checks and one fresh real regeneration, then RIR_MANIFEST.json, RIR_SUMMARY.csv, README.md and RESULTS.md. Canonical WAVs are not rewritten. |
| s2_finalize.py package | Passed library validation plus reviewed plots -> one ZIP, inventory, hash list and external ZIP checksum/receipt. |

All scripts live under simulation/scripts. Imported S1 helpers remain unchanged. Environment used: Python 3.12.7, NumPy 1.26.4, SciPy 1.13.1, soundfile 0.13.1, matplotlib 3.10.7, psutil 5.9.0 in the existing Anaconda base.

## PowerShell: verify/resume this exact completed pair

```powershell
$s2Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s2Report = Join-Path $s2Sim 'reports\S2\20260908T203309Z'
$s2Library = Join-Path $s2Sim 'rir_library\v1'
$s2Python = 'C:\Users\amiri\anaconda3\python.exe'
& $s2Python "$s2Sim\scripts\s2_code_gate.py" --report $s2Report
& $s2Python "$s2Sim\scripts\s2_run.py" --report $s2Report --library $s2Library --workers 4
```

## Anaconda Prompt / Command Prompt: verify/resume

```bat
set "S2SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S2REPORT=%S2SIM%\reports\S2\20260908T203309Z"
set "S2LIBRARY=%S2SIM%\rir_library\v1"
set "S2PYTHON=C:\Users\amiri\anaconda3\python.exe"
"%S2PYTHON%" "%S2SIM%\scripts\s2_code_gate.py" --report "%S2REPORT%"
"%S2PYTHON%" "%S2SIM%\scripts\s2_run.py" --report "%S2REPORT%" --library "%S2LIBRARY%" --workers 4
```

Expected completed-run behavior is zero newly processed and 121 resumed IDs in the new execution receipt. This was verified during completion. Input/config/code/scope and output hashes must match; a changed identity is not silently repaired. Run commands sequentially because they share report/cache state. Keep this report paired with v1. A different method/input set requires both a new report directory and the next library version, not a different library path attached to old receipts.

For a fresh authorized run, set new report/library paths, then run s2_assess.py, s2_controls.py, s2_code_gate.py and s2_run.py in that order. For the controls step use:

```powershell
& $s2Python "$s2Sim\scripts\s2_controls.py" --report $s2Report
```

```bat
"%S2PYTHON%" "%S2SIM%\scripts\s2_controls.py" --report "%S2REPORT%"
```

Do not use that controls command on this already frozen report. Final-policy changes require rerunning controls and regenerating affected outputs in a new version.

## Rebuild presentation and handoff from this completed run

These commands update reports/plots and replace the same-named handoff ZIP. Preserve a delivered ZIP and its external receipt if its exact historical bytes matter. They leave canonical WAVs untouched.

PowerShell:

```powershell
& $s2Python "$s2Sim\scripts\s2_finalize.py" build --report $s2Report --library $s2Library --started-utc '2026-09-08T20:33:09Z'
& $s2Python "$s2Sim\scripts\s2_plots.py" --report $s2Report
# Inspect the PNGs; update VISUAL_QA.json only to record an actual review.
& $s2Python "$s2Sim\scripts\s2_finalize.py" package --report $s2Report --library $s2Library --started-utc '2026-09-08T20:33:09Z'
Get-FileHash -Algorithm SHA256 "$s2Sim\handoffs\S2_ALL_RIRS_CHATGPT_HANDOFF_20260908T203309Z.zip"
```

Anaconda Prompt / Command Prompt:

```bat
"%S2PYTHON%" "%S2SIM%\scripts\s2_finalize.py" build --report "%S2REPORT%" --library "%S2LIBRARY%" --started-utc "2026-09-08T20:33:09Z"
"%S2PYTHON%" "%S2SIM%\scripts\s2_plots.py" --report "%S2REPORT%"
rem Inspect the PNGs; update VISUAL_QA.json only to record an actual review.
"%S2PYTHON%" "%S2SIM%\scripts\s2_finalize.py" package --report "%S2REPORT%" --library "%S2LIBRARY%" --started-utc "2026-09-08T20:33:09Z"
certutil -hashfile "%S2SIM%\handoffs\S2_ALL_RIRS_CHATGPT_HANDOFF_20260908T203309Z.zip" SHA256
```

The handoff includes all 121 canonical WAVs, one authoritative manifest, summary/config/readme/results, four QC plots, small code/test evidence and SHA-256 inventory. No original captures, S1 alternate WAVs, model weights or vendor packages are included. An external .sha256/.receipt.json hashes the ZIP without a self-hash cycle.

## Resource and validation limits

One inner numerical thread, four CPU workers, 16 GiB task-RSS budget, at least 16 GiB system RAM available, 5 GiB output/scratch budget and 50 GiB free-disk reserve. The 15-second monitor provides sampled cooperative guards, not hard OS memory limits; source/candidate arrays are bounded per worker. Only this task's workers/files are closed. No original data or unrelated cache/process is removed.

One RIR means one four-channel file. The manifest keeps original acquisition status separate from extraction outcome and HIL readiness. Same-sweep residuals do not establish WER/DER, precise angle/distance accuracy, acoustic repeatability, ideal diffuse fields or physical replay. This task stops after the library/handoff.
