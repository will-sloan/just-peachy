# S1 timing and four-channel RIR pilot

S1 applies the supplied room-scope update, tests the extractor on known-FIR synthetic fixtures, and extracts only the revised 12-record development pilot. It does not run S2, hardware control, H2 inference, training, or scene synthesis. The active set is 121 candidates; six exact `Loeb Caf` records and the original 52 audit exclusions stay excluded, including noise use. `Upper Loeb` is retained.

Completed run: `reports/S1/20260908T185148Z`. Full responses are under `derivatives/S1/20260908T185148Z`. Four provisional limited-band/tail candidates and eight timing-review candidates were created; none is simulation-ready. Both supplied packs and completed S0 files remain immutable. The current overlay is `config/scope_and_room_context.v3.json`; it preserves ±5 degree label uncertainty, original signed centers, both bound distance corrections and unknown numeric geometry. The five qualitative room descriptions are in CONTEXT.md and the S1 report, not used as numeric extraction inputs.

## Dependencies and inputs

Use existing `C:\Users\amiri\anaconda3\python.exe`: Python 3.12, NumPy 1.26.4, SciPy 1.13.1, soundfile 0.13.1, matplotlib 3.10.7 and psutil 5.9.0. No installation is needed. The H2 environment is unchanged. Read the explicit selected-input manifest; never collect WAVs recursively to determine eligibility.

`s1_prepare.py` consumes the hash-bound S0 catalogue, supplied scope overlay and revised selection; it produces active/selected manifests, binding receipts, initial config/QC policy and updated context. `s1_signal.py` contains pure signal functions: common reference-clock mapping, ESS inverse, noise/decay/tail metrics and bounded regularized cross-check. `s1_synthetic.py` uses an independent resampler and known four-channel FIR to test gain, timing, ordering, drift signs, noise, late reflections and marker contamination before real scoring.

## Initial commands used: PowerShell

The following preparation/synthetic commands document the initial execution. **Do not repeat initialization against this completed run:** it rewrites the overlay/configuration and would invalidate analysis bindings. Use the resume commands below to verify completed work. A changed method or new run requires a new report/derivative identity and later authorization; this README does not authorize S2.

```powershell
$s1Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s1Report = Join-Path $s1Sim 'reports\S1\20260908T185148Z'
$s1Pack = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\Just_Peachy_S1_Start_With_Room_Update\Just_Peachy_S1_Start_Pack'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\anaconda3\python.exe' "$s1Sim\scripts\s1_prepare.py" --report $s1Report --update-pack $s1Pack
& 'C:\Users\amiri\anaconda3\python.exe' "$s1Sim\scripts\s1_synthetic.py" --report $s1Report
```

## Initial commands used: Anaconda Prompt / Command Prompt

```bat
set "S1SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S1REPORT=%S1SIM%\reports\S1\20260908T185148Z"
set "S1PACK=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\Just_Peachy_S1_Start_With_Room_Update\Just_Peachy_S1_Start_Pack"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\anaconda3\python.exe" "%S1SIM%\scripts\s1_prepare.py" --report "%S1REPORT%" --update-pack "%S1PACK%"
"C:\Users\amiri\anaconda3\python.exe" "%S1SIM%\scripts\s1_synthetic.py" --report "%S1REPORT%"
```

## Completed implementation and outputs

| Component | Inputs, purpose and outputs |
| --- | --- |
| scripts/s1_run.py | Reads only the selected 12 bound inputs, config/QC and passed synthetic gate. One coordinator writes versioned WAV/NPZ/metric receipts, status/heartbeat and execution/resource evidence. Initially used --limit 1 --workers 1, then --limit 12 --workers 4. |
| scripts/s1_signal.py | Imported numerical library. Known reference plus simultaneous four-channel samples to marker/clock estimates, linear ESS diagnostics, shared candidate window, noise/support/delay/level/residual metrics. No standalone command. |
| scripts/s1_plots.py | Reads saved metrics/plot_data.npz only. Produces 12 diagnostic PNGs, one overview and filter-only flat-band characterization. Does not reread recordings or change WAVs. |
| tests/test_s1.py | Six targeted tests. S1_REPORT environment variable selects the saved run; checks signed GCC, sinc gain, exact scope/distances, revised pilot, provisional contracts and candidate sample hashes. |
| scripts/s1_package.py | Takes report, derivative root and actual stage start. Checks binding receipts, reads passed tests and visual review, generates detailed report/summary/manifests/next-inputs/resources, then creates and validates a ≤50 MiB ZIP. No extraction or device access. Reporting prose is specific to this executed pilot and must be revised if results change. |

The exact run output names and relative/full/alternate time origins are in rir_pilot_manifest.json. Per record, attempt_001 contains full_ess_diagnostic.wav, alternate_clock_full_diagnostic.wav, candidate_4ch.wav, plot_data.npz and metrics.json; orders 1/12 also contain fd_crosscheck_4ch.wav. FLOAT32 WAVs retain MIC0–MIC3 scaling; no peak normalization. The handoff contains all 12 small candidates and local paths/hashes for full diagnostics. Full WAVs, raw captures, NPZ intermediates, model weights and enrollment data stay out of the ZIP.

Initial QC was written before real pilot scoring. Synthetic fixtures validate code, not acoustic repeatability. No numerical policy threshold was retuned after real outcomes. See METHOD_AND_LIMITATIONS.md for the unused tail-policy field and RSS/clock-flag interpretation cautions.

## Verify/resume: PowerShell

These commands safely validate an unchanged completed extraction. Expected runner result: 12 resumed, zero newly processed (recorded in a new execution receipt). Run only one S1 command at a time because the coordinator/cache are shared.

```powershell
$s1Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s1Report = Join-Path $s1Sim 'reports\S1\20260908T185148Z'
$s1Derived = Join-Path $s1Sim 'derivatives\S1\20260908T185148Z'
$s1Python = 'C:\Users\amiri\anaconda3\python.exe'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
$env:S1_REPORT=$s1Report
& $s1Python "$s1Sim\scripts\s1_run.py" --report $s1Report --derived $s1Derived --limit 12 --workers 4
& $s1Python -m unittest discover -s "$s1Sim\tests" -p test_s1.py -v
```

## Verify/resume: Anaconda Prompt / Command Prompt

```bat
set "S1SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S1REPORT=%S1SIM%\reports\S1\20260908T185148Z"
set "S1DERIVED=%S1SIM%\derivatives\S1\20260908T185148Z"
set "S1PYTHON=C:\Users\amiri\anaconda3\python.exe"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set NUMEXPR_NUM_THREADS=1
set "S1_REPORT=%S1REPORT%"
"%S1PYTHON%" "%S1SIM%\scripts\s1_run.py" --report "%S1REPORT%" --derived "%S1DERIVED%" --limit 12 --workers 4
"%S1PYTHON%" -m unittest discover -s "%S1SIM%\tests" -p test_s1.py -v
```

The current initial and revised selection/configuration are hash-bound. Resume requires matching inputs, code, QC, scope and every saved WAV hash. It does not equate a changed file with the former result. The runner retains prior derivative attempt directories for a changed resume key, but a future intentional method change should use a new reviewed run rather than replacing this completed report. Any missing/mismatched input blocks processing. The runner cannot expand beyond 12.

## Regenerate presentation/package from existing evidence

The following commands only render plots and rebuild the report/package. They replace derivative presentation files and the same-named ZIP; preserve the delivered ZIP/receipt if you need that exact historical snapshot. The report requires METHOD_AND_LIMITATIONS.md, the observed unit_test_results.json and visual_qa.json already present in this completed run. These evidence receipts must not be invented for a new run.

PowerShell, after the variables above:

```powershell
& $s1Python "$s1Sim\scripts\s1_plots.py" --report $s1Report
# Inspect the PNGs and update visual_qa.json if the plots or code changed.
& $s1Python "$s1Sim\scripts\s1_package.py" --report $s1Report --derived $s1Derived --started-utc '2026-09-08T18:51:48Z'
Get-FileHash -Algorithm SHA256 "$s1Sim\handoffs\S1_CHATGPT_HANDOFF_20260908T185148Z.zip"
```

Anaconda Prompt / Command Prompt, after the variables above:

```bat
"%S1PYTHON%" "%S1SIM%\scripts\s1_plots.py" --report "%S1REPORT%"
rem Inspect the PNGs and update visual_qa.json if the plots or code changed.
"%S1PYTHON%" "%S1SIM%\scripts\s1_package.py" --report "%S1REPORT%" --derived "%S1DERIVED%" --started-utc "2026-09-08T18:51:48Z"
certutil -hashfile "%S1SIM%\handoffs\S1_CHATGPT_HANDOFF_20260908T185148Z.zip" SHA256
```

The packaging script checks CRC, exact ZIP membership, payload SHA-256, candidate count/identities, exclusions, provisional flags, scratch usage and free-disk reserve. FILE_INVENTORY.json covers payloads; SHA256SUMS.txt also hashes that inventory. The external .sha256/.receipt.json files and package_validation.json attest the ZIP without circular self-hashing.

## Resource behavior and next gate

At most four workers, one inner numerical thread, CPU only. A 15-second heartbeat samples task RSS, available RAM and disk; thresholds are 16 GiB task RSS, at least 16 GiB system RAM available, 5 GiB local derivatives and 50 GiB free disk. They are cooperative sampled checks, not hard operating-system memory limits. The pool exits and closes its own handles. Existing Anaconda packages are used; no H2 or system package change is required.

Fresh S1 disk snapshots show about 449 GiB free on the Kingston G: SSD; the WD_BLACK C: SSD remains above the 50 GiB reserve. Use resource_after.json for exact current-run bytes/timestamp. D: is now mostly empty but is an HDD. This pilot reads inputs in place and does not move data.

Read S1_REPORT.md and NEXT_PHASE_INPUTS.md in the completed report directory. Review the eight clock cases and freeze the timing/band/tail policy before separately authorizing S2. All candidates remain provisional, qualified_rir_available=false, simulation_ready=false. No physical XVF action, full-121 extraction, speech synthesis, H2 inference, model training or deployment is included here.
