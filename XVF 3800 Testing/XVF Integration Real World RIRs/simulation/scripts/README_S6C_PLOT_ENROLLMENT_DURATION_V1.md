# S6C enrollment-duration figure

This script creates one two-panel scientific figure from the existing all-240 naming aggregate for C141–C146. It checks the exact completed receipt and CSV bytes, all 60 roster/output/status rows, integer sample partitions and constant within-roster denominators. It performs unit conversion only; it does not replay predictions, score audio or load models.

The V2 output corrects caption wording after independent numerical review: each roster has 14 people (9 CMU and 5 HiFiTTS), 28 across the disjoint rosters. Whole-clip material, evidence-window counts and templates change alongside duration. V1 source/README and related drafts are preserved under staging/s6c/20260910T123540Z/figure_sources/before_enrollment_caption_v2. Plotted data and figure construction are unchanged. Use a fresh enrollment_duration_v2 output name for the revised caption; the example V1 namespace below already exists and must not be reused.

Inputs: the pinned full_n01_common_duration_names_v3/NAME_ANALYSIS_RECEIPT.json and its PROFILE_NAME_RESULTS.csv, plus this script and README. Outputs in a fresh figures namespace: PNG, editable SVG, exact integer PLOT_DATA.json, CAPTION.md and FIGURE_RECEIPT.json. Inspect the PNG after generation and retain a separate visual-review record. Existing outputs are never overwritten.

The left panel divides correct-name samples by enrolled sole-speech samples. The right panel divides withheld wrong-known samples by 16,000 to show source-supported seconds. These are existing modeled source-support naming measurements, not actual wall-clock display exposure. No error bars or population-significance claim is added. Four roster/output lines remain separate; no route is selected after seeing a scene.

Use the existing analysis environment with Matplotlib; no dependency installation is required.

PowerShell:

    $s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
    Set-Location -LiteralPath $s6cSim
    & 'staging\s5_text_metrics\analysis_env\Scripts\python.exe' -B 'scripts\s6c_plot_enrollment_duration_v1.py' --output 'reports\S6C\20260910T123540Z\figures\enrollment_duration_v1'

Anaconda Prompt or Windows Command Prompt:

    cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
    "staging\s5_text_metrics\analysis_env\Scripts\python.exe" -B scripts\s6c_plot_enrollment_duration_v1.py --output reports\S6C\20260910T123540Z\figures\enrollment_duration_v1

For a later rerun, choose a fresh child name under this run's figures directory. A source-binding or population failure stops before figure creation. Preserve any partial output from later plotting failures. This figure is one of the maximum six plots allowed in the final compact handoff.
