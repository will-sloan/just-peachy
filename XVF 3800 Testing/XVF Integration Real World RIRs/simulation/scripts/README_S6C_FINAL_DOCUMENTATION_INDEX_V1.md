# Current local code and README index

Purpose: create a compact current documentation catalog for the final handoff. It records paths, byte counts, SHA256 hashes and maintained README mappings for all immediate `SIM/scripts/s6c_*.py` and `test_s6c_*.py` files plus the ten explicit S6C application targets from the earlier documentation census. Retained obsolete/draft filenames are listed as current local files, not presented as executed versions.

Inputs: `documentation_coverage/working_v1/RECEIPT.json`, its coverage CSV, all explicit top-level `*ADDENDUM*.json` documents, current local code/README buffers, and the four-condition actual model-free invocation rollup/receipts. The original snapshots and addenda are unchanged. Each input is capped at8MiB. No model, audio, native log, prediction or score-value table is read. No audited code or documented command is executed.

Mapping priority: exact conventional adjacent README, previous explicit code-to-README mapping using its current bytes, then a README explicitly mentioning the source filename. Missing mappings and missing PowerShell/CMD labels are reported as gaps. Labels are a documentation presence check, not proof that all commands run or that every input/output description is semantically complete. Earlier documented caveats remain in the index; occupied historical output paths require fresh namespaces.

Outputs: a fresh child of `documentation_coverage` containing `CODE_README_INDEX.json` and `RECEIPT.json`. The compact index deduplicates README bindings and includes current code mappings, old census hashes for comparison, original addenda bindings, and source-frozen application authority examples. It contains no helper bodies. All input buffers and script filename membership are checked again before publication. The result is a point-in-time local catalog, not a global execution census, historical source-parity certificate or whole-study acceptance. Later source additions need an additive refresh.

The original execution epochs, completed native receipts and final physical inventory remain the authorities for which code actually ran. In particular, B36 uses preserved S6B epoch2; C operating commands use preserved S6C epoch4. Current local files cannot replace these generations merely because they have similar names. The completed operating validation provides those source comparisons separately.

PowerShell, using the existing interpreter without installation or activation:

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edgePython -B "$simRoot\scripts\s6c_final_documentation_index_v1.py" --output "$simRoot\reports\S6C\20260910T123540Z\documentation_coverage\final_current_v1"
```

Anaconda Prompt / Windows CMD:

```bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6C_SIM%\scripts\s6c_final_documentation_index_v1.py" --output "%S6C_SIM%\reports\S6C\20260910T123540Z\documentation_coverage\final_current_v1"
```

Choose a fresh output suffix on reproduction. Existing outputs are not overwritten; no frozen source/README or study output is edited. This helper includes itself and this README in the current catalog. No final acceptance flag is created.
