# Arrival-boundary diagnostic figure

Purpose: render one compact scientific figure from the already completed and independently reviewed C105/O0 timing diagnosis. No native execution, new policy replay, metrics recomputation, source audio, model payload or online research is involved.

Inputs are the fixed hashes of `native_timing_diagnosis_v1/RESULT.json` and `independent_review/NATIVE_TIMING_ROOT_REVIEW_V1.json`. The figure centers each source's observations on that source's ASR16 modeled availability; it does not align their UTC clocks. Numeric checks reproduce the reported -24.1741ms and +1.1398ms mature-versus-ASR offsets and retained final labels.

Outputs in a fresh explicit directory are PNG/SVG versions of the same figure, exact PLOT_DATA.json, CAPTION.md and FIGURE_RECEIPT.json. The final receipt initially marks visual review pending; root must inspect the rendered PNG and write a separate visual-review receipt before delivery. Existing output directories are refused. This is one outcome-selected diagnostic, not population accuracy evidence or actual paced timing.

PowerShell:

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& (Join-Path $s6cSim 'staging\s5_text_metrics\analysis_env\Scripts\python.exe') (Join-Path $s6cSim 'scripts\s6c_plot_arrival_boundary_v1.py') --output (Join-Path $s6cSim 'reports\S6C\20260910T123540Z\figures\arrival_boundary_v2')
```

Anaconda Prompt / Windows CMD (use this existing analysis environment with Matplotlib 3.10.7; no installation needed):

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%S6C_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%S6C_SIM%\scripts\s6c_plot_arrival_boundary_v1.py" --output "%S6C_SIM%\reports\S6C\20260910T123540Z\figures\arrival_boundary_v2"
```

The exact native EDGE interpreter is unnecessary for this static plotting task and does not contain Matplotlib. Model inference always continues to use its admitted native environment. Changing figure layout after publication requires preserving the old outputs and a new figure directory.


Figure version 2 corrects label and caption spacing only. Version 1 and its bound source/README are preserved under staging/figure_sources/before_spacing_v2. Numeric inputs, ordering and clock interpretation are unchanged.
