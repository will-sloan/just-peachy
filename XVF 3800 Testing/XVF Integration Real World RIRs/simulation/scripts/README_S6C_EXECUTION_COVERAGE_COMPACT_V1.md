# Compact complete execution coverage

Purpose: export every one of the5891 observed physical attempts into a smaller package-facing CSV. No outcome filter, census, scoring, model/audio read or source mutation occurs. The original full CSV and JSON remain immutable.

Input: the exact reviewed final physical projection RESULT (SHA db85900c955f1d0cf4634f7a4a41d68e7fd999f4225bc5f13715c6b8eeb21ccd) and its bound typed PHYSICAL_ROWS.json. All38 output fields are explicit in FIELDS plus two lineage fields. Candidate/routes/case/repetition/epoch/kind/status, observed native/acceptance/guard states, owner identity, clocks/source duration, model-load/cache facts, cue/gallery condition, error and stable original physical/row identities are retained. Missing original fields are distinguished from present null using the JSON bitmap; scalar null is an empty CSV cell, booleans are true/false. Historical missing native_session_complete is unavailable, never inferred false. No exit code or acceptance is invented from status.

Outputs beside RESULT: EXECUTION_COVERAGE_COMPACT.csv and COMPACT_CSV_EXPORT_RECEIPT.json. Packaging may rename this CSV to EXECUTION_COVERAGE.csv; the receipt retains its original path/hash. Every row's FULL_PHYSICAL_SOURCE dependency ID maps through the receipt to exact full projection and its pinned raw source. source_row_pointer and source_row_sha256 identify the original raw physical row. Verbose nested provenance, event counters and model/epoch/input references stay in those indexed sources. The virtual unknown observer is retained in the projection result/owner/failure outputs, not fabricated as another physical attempt. No extra attempt counts are derived from cache references.

Seven tiny checks cover failure/error, unknown native state, false owner state, missingness and duplicate IDs. Actual export validates exact count/order and roundtrips every selected value. Reported zlib size is a packaging estimate, not the final ZIP size. Flat standard CSV uses Python's csv module, consistent with the earlier export's documented Artifact Tool CSV limitation; no workbook calculations are involved.

## PowerShell

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B -c "import s6c_execution_coverage_compact_v1 as m; print(m.tests())"
& $edgePython -B s6c_execution_coverage_compact_v1.py --result "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\final_physical_projection_v1\RESULT.json"
```

## Anaconda Prompt / CMD

Use the existing interpreter directly; no install or environment activation.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import s6c_execution_coverage_compact_v1 as m; print(m.tests())"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_execution_coverage_compact_v1.py --result "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\final_physical_projection_v1\RESULT.json"
```

Outputs use exclusive creation. Do not overwrite an existing export to repeat the command.
