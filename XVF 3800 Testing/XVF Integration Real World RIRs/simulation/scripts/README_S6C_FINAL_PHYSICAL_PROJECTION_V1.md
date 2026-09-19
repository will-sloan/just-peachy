# Compact physical census projection

Purpose: produce a complete, compact machine-readable projection of the final census, without repeating discovery or native work. Every one of5891 observed attempts remains represented. Original COMPLETE, STARTED and failed-outer/native-complete statuses are preserved. All7412 owner observations remain separate, including7411 concrete closed observations and the null-identity virtual observer exception.

Inputs: exact final inventory JSON SHA eb22fabc22733599bcdf7303bf2d9cbb5fa7464629e18c5bbfae558716f43fb9 and its original51,344,039-byte physical metadata JSON SHA0368a24785e15576e4fa1312e0c9ebe8b9574329ddb992ad462852f141452c71. Only this explicitly pinned large input is admitted above32MiB. Parsing and hash verification use the same buffer; no input/session/audio/model path in the records is followed.

Outputs in a fresh execution_inventory child: PHYSICAL_ROWS.json (typed all-row projection), OWNER_OBSERVATIONS.json, UNAVAILABLE_AND_FAILURES.json, MODEL_AND_CACHE_RECEIPTS.json, EXECUTION_COVERAGE_MATRIX.json and RESULT.json. Each output remains below the unchanged final assembler32MiB limit. The original large JSON remains locally indexed by exact path/hash and per-row pointer/digest.

Each candidate's physical ID, status, exact original error text, route, condition fields, owner, source declarations, event-count/load/cache metadata and receipt bindings are copied. Missing fields remain null plus an explicit missing_original_fields list. No missing field becomes zero, no failed outer becomes scientific success, and no index reuse becomes a physical attempt. The native-session total is inherited from the census; the optional native_session_complete field is not summed across historical rows.

The CSV matrix is an intermediate for the final flat EXECUTION_COVERAGE.csv export. Scalar nulls are represented as empty CSV fields, with JSON columns preserving explicit null versus missing. No formulas, merged headers, workbook styling or score calculations are introduced.

PowerShell (exact existing interpreter, no activation):
```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B -c "import s6c_final_physical_projection_v1 as p; print(p.checks())"
& $edgePython -B s6c_final_physical_projection_v1.py --output "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\final_physical_projection_v1"
```

Anaconda Prompt / CMD:
```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import s6c_final_physical_projection_v1 as p; print(p.checks())"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_physical_projection_v1.py --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\final_physical_projection_v1"
```

The first command uses eight tiny missing/false/unknown/failed/error/invalid-owner guards only. The second reads the declared metadata once for projection and writes a fresh immutable namespace. Choose a fresh suffix for reproduction; existing output is never overwritten. Source-only import does not read the census. Independent review and final assembly admission remain distinct from projection completion. whole_study_complete stays false.

The pre-review source/README are preserved in STAGING/final_physical_projection/before_error_field_v1. The reviewed correction adds the original error field and one tiny preservation fixture; no input or original result was changed.
