# S6C separate V3 scorer admission

Shared model-free admission functions used by core/name V3. It contains no metric or predictor implementation. Inputs are explicitly named paths and expected SHA256 values, with repeatable arguments for append-only candidate amendments and completed evaluator gallery maps. Relative paths resolve against this S6C report. No directory auto-discovery, no implicit latest version, no replacement of existing candidates/map rows. A current source binding is checked before consuming it; it does not lock arbitrary external writers after admission. Original native model receipts remain transitively bound by predictions, as in V2.

Inputs: exact prediction index (path relative to reports/S6C/20260910T123540Z), canonical bank/support, original184-candidate declarations, and the explicit additions below. The current two amendments yield234 registered labels, not234 distinct algorithms or neural caches. Names C143/C146 retain alias semantics. Outputs: new requested report subdirectory with score JSONs, complete coverage, per-scene/turn/aggregate tables and a source-bound completion receipt. Existing output directories/receipts cannot be overwritten; do not use a V2 output name. No models, hardware, downloads or source edits.

PowerShell (choose an existing exact prediction index; the example is a small already completed original panel):

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_analysis_v3.py --test
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_analysis_v3.py --index epoch2/N01_panel_v1_PREDICTION_INDEX.json --output-subdir n01_core_v3_example --require-complete --registry-extension design/COMMON_ROSTER_DURATION_AMENDMENT_V1.json b8d25fc00366242bd38bb1e56f16cd30dd1aa78262b8a1eda9e2a2fe4068671d --registry-extension design/FRESH_EVIDENCE_FOLLOWUP_AMENDMENT_V1.json b899191bccf897689b5ea543b05367f2b62d60fb481e7e2f3255246a7afe2b75 --expected-candidates 234
```

Anaconda Prompt / CMD uses the pinned analysis interpreter, not the active Conda environment:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_analysis_v3.py --test
"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_analysis_v3.py --index epoch2/N01_panel_v1_PREDICTION_INDEX.json --output-subdir n01_core_v3_example --require-complete --registry-extension design/COMMON_ROSTER_DURATION_AMENDMENT_V1.json b8d25fc00366242bd38bb1e56f16cd30dd1aa78262b8a1eda9e2a2fe4068671d --registry-extension design/FRESH_EVIDENCE_FOLLOWUP_AMENDMENT_V1.json b899191bccf897689b5ea543b05367f2b62d60fb481e7e2f3255246a7afe2b75 --expected-candidates 234
```

These commands are examples, not evidence that a V3 scoring run executed. `--test` runs only bounded fixtures. Without extensions the core declaration remains184; set `--expected-candidates` to the exact explicit amended count when adding files. Full240 confirmation is distinct from completion of a smaller declared index. Scorer metadata never enters the native anonymous association pipeline. No result here qualifies desktop timing as CM5 performance.

