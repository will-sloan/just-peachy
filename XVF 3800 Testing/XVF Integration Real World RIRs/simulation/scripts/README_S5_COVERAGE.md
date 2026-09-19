# S5 metadata coverage and dependency review

`s5_coverage.py` independently reconciles the full frozen S4.5 bank with the S5 pack's exact development allowlist, protected reserve IDs, four exclusive scoring populations and room/RIR table. It does not import a runner, scorer, audio package or model. It does not open source/RIR/output audio, predictions, event journals, embeddings or task-metric files. All 60 reserve entries are inspected only as metadata. It does not alter any S4.5 evidence or the V10 Word guide.

Inputs are the extracted `Just_Peachy_S5_Codex_Pack/Just_Peachy_S5_Codex_Pack`, its checksums and standalone Downloads prompt, `Downloads/XVF_Measurement_V10.docx`, the existing S4.5 handoff ZIP, canonical `scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json`, `rir_library/v1/RIR_MANIFEST.json`, bound source/legacy/noise manifests, and the S4.5 acceptance/rights/final source and conservation receipts. The active bank, RIR manifest and V10 SHA identities are fixed in the script. Large source/RIR files are not rehashed: their saved identities are joined through the freshly hashed qualified source and 121-WAV conservation receipts. The acceptance map must match the prior source review's exact 240 case-receipt bindings. This reuses established integrity evidence and does not pretend it is a new waveform audit.

The supplied S5 prompt contains a malformed **57-character** RIR hash. The current manifest and both earlier qualified final source/conservation receipts agree on the established full SHA-256 `468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546`. The utility records the exact original typo and its receipt-backed resolution in `documented_input_discrepancies`, leaving the prompt and library unchanged. An unrecognized different hash blocks reconciliation; this is not a general hash-mismatch bypass.

Outputs go only to `simulation/reports/S5/20260909T130308Z`:

- `RIR_COVERAGE.csv`: all 121 library records, including the explicitly excluded clock-sensitive path; original/effective distances, signed bearing, manual uncertainty, missing geometry, development/reserve counts, and development-used/reserve-only/deferred disposition.
- `SCENE_COVERAGE.csv`: 240 metadata rows, exact development population or protected-reserve marker, room/pose/obstruction, source quality and pseudonymous IDs, prompt/book/noise/RIR groups, requested level/SNR/SIR and measured-path source policy. Lists/dicts are JSON inside CSV cells. Full transcripts and model results are omitted.
- `DEPENDENCY_BLOCKS.json`: deterministic union of explicit matched-pair and matched-group IDs across all development scenes, primary-member projections, fixed-room memberships, and shared-speaker/clip/prompt/book/RIR/noise dependency components. These are input-based proposals for the coordinator's frozen scoring protocol, not new significance results.
- `INPUT_COVERAGE_REVIEW.json`: exact input/export/code/README bindings, exclusive population reconciliation, room/speaker/quality/noise/level counts, protected metadata-access scope and known limits.

Use the existing Anaconda Python; only its standard library is required. From PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s5_coverage -v
& 'C:\Users\amiri\anaconda3\python.exe' s5_coverage.py --validate-only
& 'C:\Users\amiri\anaconda3\python.exe' s5_coverage.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s5_coverage -v
"C:\Users\amiri\anaconda3\python.exe" s5_coverage.py --validate-only
"C:\Users\amiri\anaconda3\python.exe" s5_coverage.py
```

`--validate-only` performs the same metadata checks and prints counts without report writes. Normal execution atomically refreshes these four S5 coverage outputs. A missing input, changed binding, or population mismatch returns exit 2 with `BLOCKED_INPUT_RECONCILIATION`; do not change source/split flags to force an expected count. Successful metadata validation returns exit 0, not a claim that any S5 model job or scoring is complete. Do not run with Python `-O`; the utility uses explicit checks, but surrounding project workflows may rely on assertions.

The unit fixtures are synthetic, use temporary files only and cover the four population rules, protected reserve metadata, unknown-noise strict-control refusal, transitive matched groups, projection after grouping, and refusal to open waveform/task-result files. They do not read production evidence or run any audio/model/USB operation.

The dated execution receipt, exact stdout/stderr and tested code/README bindings are retained in `simulation/staging/s5_coverage/v1/TEST_RECEIPT.json`. Actual validation/export receipts there are distinct from synthetic fixture success. The current reconciled graph has131 matched blocks over180 development scenes and85 primary blocks over117 scenes:58 singletons,22 pairs and5 triples. All primary observations connect when people, content, RIR and noise dependencies are combined. The developer-facing block interface is `blocks[{block_id,scene_ids,room_table,primary_scene_ids,matched_keys}]`; `dependency_diagnostics.speaker.primary_components` provides the separate speaker-connected sensitivity groups. Regenerating the graph does not authorize changing a protocol already frozen from it.

Expected reconciled development populations are 117 complete-reference nonoverlap, 36 complete-reference overlap, 19 incomplete ambient and 8 strict controls, exclusively totaling180. The39 real-noise development scenes overlap those populations. Only7 development scenes are upright and7 obstructed. Development uses33 of120 eligible RIRs across4 rooms; all240 use39 across5 contexts, with81 unused eligible paths. Unused paths are deferred, not failures or proven equivalent. Both original100m entries keep effective1.00m from the user's100cm correction. Manual±5degrees is measurement uncertainty, not XVF accuracy, an automatic tolerance or injected jitter; front/rear folding and missing3D coordinates remain.

Explicit matched blocks may be resampled conditionally within the4 fixed rooms while retaining both outputs and complete matched contrasts. Shared people, clips, text, books, RIRs and noise cross those blocks. A graph that collapses all dependencies may leave no independent replicates; speaker-component/leave-room-out descriptive sensitivities must accompany any conditional interval. Do not call this population-independent inference or blind preregistration:24 development scenes were already inspected in S4.5. CMU basenames are not universal prompt IDs; normalized native text/book/byte groups are the qualified keys. Neither corpus metadata nor counts establish biometric human uniqueness, demographic causation, anechoic speech, enrollment accuracy or downstream training rights.
