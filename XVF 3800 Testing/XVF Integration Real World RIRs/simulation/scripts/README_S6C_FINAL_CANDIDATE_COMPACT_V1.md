# Compact final candidate export

Purpose: produce a package-facing CSV containing all240 final candidates from the exact completed disposition assembly. The full20MB CSV and28MB route evidence remain immutable and locally indexed. No score, model, census or selection is rerun.

Input: final_disposition_v1/RECEIPT.json pinned SHA8283a245fced3dd4be45b0b6b988cca2145b48cbe108a9961a34b5be89ddf1f0 and its bound full candidate CSV. The seventeen columns preserve candidate/family/recipe/route identity, original registration row/settings provenance, final scientific disposition, full final interpretation and limitations with all evidence IDs, and exact operating bundles. Original historical registration wording remains explicitly historical. The final fields provide the current decisions.

Output beside the input: CANDIDATE_DISPOSITION_COMPACT.csv and COMPACT_EXPORT_RECEIPT.json. Packaging may use a shorter canonical archive filename. FULL_FINAL_CANDIDATE_EVIDENCE maps via the receipt to exact local full candidate CSV and route JSON. Each output row supplies the canonical sorted-key JSON SHA256 of the entire original candidate CSV row and a matching route-JSON array pointer. Large per-evidence source rows remain retrievable under those bindings. Every evidence ID is retained in final_supported_interpretation_and_gaps; no evidence body is represented as an additional experiment. Aliases retain no propagated execution. Whole-study acceptance remains false.

Four tiny checks cover alias identity/disposition, whole-row digest and duplicate rejection. Actual export checks240 unique rows and exact selected-value CSV roundtrip. The CSV uses Python's standard csv module; no workbook calculations are involved. zlib size is a packaging estimate only.

## PowerShell

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B -c "import s6c_final_candidate_compact_v1 as m; print(m.tests())"
& $edgePython -B s6c_final_candidate_compact_v1.py --receipt "$simRoot\reports\S6C\20260910T123540Z\candidate_disposition\final_disposition_v1\RECEIPT.json"
```

## Anaconda Prompt / CMD

Use the existing interpreter directly, without installation or activation.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import s6c_final_candidate_compact_v1 as m; print(m.tests())"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_candidate_compact_v1.py --receipt "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\candidate_disposition\final_disposition_v1\RECEIPT.json"
```

Output files use exclusive creation; do not overwrite existing results.
