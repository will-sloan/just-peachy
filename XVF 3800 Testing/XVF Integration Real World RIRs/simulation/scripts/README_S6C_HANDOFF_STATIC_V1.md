# Static S6C source and transcript appendix

`s6c_handoff_static_v1.py` creates a metadata-only handoff appendix. It is independent of active native workers, scorers and APP code. It does not load models, read raw audio/corpora, use a gallery, contact hardware or score predictions.

Inputs are the exact pinned sealed S6B artifact index (L0119 inputs, L0159 scene bank), inherited transcript coverage/support, completed S6C E/C/Q and enrollment receipts, local rights audit, and canonical RIR/S0/S2 metadata. Every consumed metadata/code buffer is SHA-256 verified before parsing. The source and normalized reference-layout helpers are extracted from two hash-pinned existing functions; their module bodies and scoring backends are never imported. Carried raw WAV/model/journal bindings are explicitly not rehashed. Old source executor aliases resolve through the preparation code admission and preserved metadata snapshot.

Outputs in the fresh directory `reports/S6C/20260910T123540Z/handoff_static_v1`:

- `SOURCE_AND_TRANSCRIPT_AUDIT.json`: counts, inherited limitations, corrections and exact consumed-source bindings.
- `ALL240_REFERENCE_COVERAGE.csv`: 240 data rows; both tap bindings appear in each scene row. This is a machine-readable audit table, not a formula workbook.
- `SOURCE_COVERAGE_RIGHTS_AND_DOMAINS.md`: readable populations, E/C/Q tiers, rights/domain limitations and complete CSV field guide.

Existing output directories are rejected. Use a new `--output` directory to repeat a collection; never overwrite a reviewed appendix. Source pins deliberately fail on changed historical files. Report-only status is not a final S6C completion or acoustic/identity accuracy claim.

## PowerShell

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_handoff_static_v1.py" --self-test
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_handoff_static_v1.py"
```

## Anaconda Prompt / Windows Command Prompt

No environment activation or package installation is required; invoke the existing interpreter directly.

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_handoff_static_v1.py" --self-test
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_handoff_static_v1.py"
```

The seven pure fixtures check exact-buffer reads, changed same-size bytes, no overwrite, and unique complete tap-grid admission. Real execution then reconciles each of777 scheduled source occurrences against canonical source/transcript/identity metadata and rechecks both tap support identities, without reading predictor outputs. Metric denominators are156 primary/4560 words,203 complete/6016 words,26 incomplete and11 empty. Word counts are per scene before tap/profile replication. Incomplete and strict-empty rows remain visible and never receive an invented complete-reference WER denominator.

The RIR check revalidates canonical metadata eligibility/disjoint exclusions, distances and unmodified angle centers. It retains raw100m and effective1m for the two user-confirmed records. Existing capture audits and extraction limitations are inherited with exact bindings; no raw measurement validation is rerun. Rights assertions are inherited, not renewed legal clearance. CSV/list fields and measurement clocks are documented in the generated summary.
