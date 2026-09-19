# Execution coverage CSV export

Purpose: export the reviewed typed census projection as one flat CSV row per observed physical attempt. This is a machine-readable research table, with no formulas or workbook styling. All5891 rows and their original statuses, conditions, source references, missing-field bitmap and owner evidence remain represented. It is not a new census or inference count.

Inputs: the exact physical projection RESULT path/SHA and its already bound CSV matrix. Outputs beside that RESULT: EXECUTION_COVERAGE.csv and CSV_EXPORT_RECEIPT.json. Every exported cell is checked by parsing the resulting CSV back and comparing the original normalized string value. Scalar nulls are blank; booleans are true/false; JSON columns preserve null and missing-field distinctions. Numeric source values retain Python's roundtrip decimal representation. Original JSON remains the typed authority.

The bundled Artifact Tool public documentation/help provides workbook XLSX/render output but no CSV export entry (`workbook.toCSV` matched none). The final flat export therefore uses bundled Python's standard CSV module. No extra XLSX is created or requested.

PowerShell:
```powershell
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B 'C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/scripts/s6c_execution_coverage_csv_v1.py' --result 'C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S6C/20260910T123540Z/execution_inventory/final_physical_projection_v1/RESULT.json' 'db85900c955f1d0cf4634f7a4a41d68e7fd999f4225bc5f13715c6b8eeb21ccd'
```

Anaconda Prompt / CMD (no activation):
```bat
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B "C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/scripts/s6c_execution_coverage_csv_v1.py" --result "C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S6C/20260910T123540Z/execution_inventory/final_physical_projection_v1/RESULT.json" "db85900c955f1d0cf4634f7a4a41d68e7fd999f4225bc5f13715c6b8eeb21ccd"
```

Existing outputs fail exclusive creation. Reproduction requires a separately prepared fresh projection namespace. No original census, source, lease, model or score file is changed.

