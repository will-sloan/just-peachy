# N6h affected closure checks

Purpose: verify only the tuple/list serialization repair with eight small checks. The actual frozen S6DSettings class and old/new pure validation functions are extracted by AST; no native application/model module is imported. All inherited functions/imports/constants are compared to the original AST, allowing only the exact closure comparison and the new serializer.

Inputs: `--source-root` containing `s6d_beam_native_run_n6h.py` and this README; immutable N6g, actual first C12v3 RESULT/closure/finalization/rejected-audit metadata and frozen settings source. Recorded audit journal hashes are reused as fixture inputs; no audio/PCM/event journal is scanned.

Outputs: fresh `--output/RECEIPT.json` with eight results and exact sources. Existing output directories are refused. The fixtures confirm actual tuple/list positive, nonempty tuple/list preservation, changed selection, nonzero depth, missing full-drain proof, changed numeric values, missing keys and nonfinite rejection. They do not accept any historical native run.

PowerShell:

```powershell
$s = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s\s6d_N6h_closure_checks_v1.py" --source-root $s --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\N6h_closure_v1\checks_FRESH'
```

Anaconda Prompt or CMD:

```bat
set "S=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -B "%S%\s6d_N6h_closure_checks_v1.py" --source-root "%S%" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\N6h_closure_v1\checks_FRESH"
```

Use a new G output suffix. For independent review, set `--source-root` to the directory of exact copied candidate files and invoke its copied fixture. No production source mutation, process/device query, model/audio run, queue or authority write occurs. The earlier 31-check admission suite is outside this affected batch and is not rerun.
