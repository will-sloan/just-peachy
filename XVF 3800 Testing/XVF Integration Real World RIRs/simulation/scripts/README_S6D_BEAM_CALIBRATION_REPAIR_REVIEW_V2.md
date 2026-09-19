# Independent calibration V2 repair review

`s6d_beam_calibration_repair_review_v2.py` reviews the exact c71f6a3f calibration freeze. It verifies every frozen source, selector, evidence-reader and author-receipt binding, copies the seven source/README files to a fresh G review tree, and runs12 targeted synthetic probes. It does not run models, physical commands, actual C extraction or production threshold fitting. Frozen and original files remain unchanged.

Inputs: `--freeze` exact SOURCE_FREEZE.json; `--output` one fresh G directory. Output: copied review sources, clearly synthetic authority examples, OBSERVATIONS.json, and INDEPENDENT_REPAIR_REVIEW_V2.json. The probes independently reproduce closure of the unnamed0.95 competitor, unrelated root status, and per-metric fits with zero joint survivors. Related checks cover bound exclusions/noQ, ambiguous populations, real selector positive controls, unique original C sources, and ambiguous winner rejection. Tiny scalar correlations stand in for already computed collection correlations; no waveform/model function is run. No root authority is issued.

PowerShell / Anaconda PowerShell Prompt:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_beam_calibration_repair_review_v2.py" --freeze "$sim\reports\S6D\20260913T195357Z\application\beam_C_calibration_source_v2\SOURCE_FREEZE.json" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_repair_independent_v2'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_beam_calibration_repair_review_v2.py" --freeze "%SIM%\reports\S6D\20260913T195357Z\application\beam_C_calibration_source_v2\SOURCE_FREEZE.json" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_repair_independent_v2"
```

Use a new output suffix if the directory already exists. This review can establish source/fixture closure only. Actual C completion, exact source/clock support, sufficient distinct negative and positive original C sources, and a separate root enablement review remain mandatory.
