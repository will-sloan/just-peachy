# Working full-bank attribution figure

Purpose: s6c_plot_attribution_v1.py plots already reviewed compact attribution aggregates in the explicit order B36, C065, C079, C122, C067, with separate O0/O1 panels. Each gray segment connects first-display-label final-word cp and latest-label cp for one configuration. Exact error counts label the endpoints; rates are the original counts divided by 6,016. This is figure three of the working S6C handoff, not final scientific or operating selection.

Inputs are the exact SHA-bound design/ATTRIBUTION_FIGURE_SPEC_V1.json, three completed original PROFILE_RESULTS tables and their ANALYSIS_RECEIPT files, plus the already completed full-anonymous/N03 review and comparison receipts. Only compact CSV/JSON metadata is read. Each exact byte buffer is checked before parsing. The script admits the original completed source counts, unique profile/tap/population rows, the selected ten routes, and both metrics' 203-scene/6,016-word denominators. It verifies reported rates against the existing integer counts. It does not import any scorer, replay policy, read individual scores or predictions, open native logs/PCM/models, or repeat the prior numerical reviews.

Outputs in a fresh direct REPORT/figures child are SOURCE_ROWS.csv with exact original selected CSV strings and source bindings, PLOT_DATA.json with integer counts and plotted percentages, attribution_tradeoffs.png, editable attribution_tradeoffs.svg, CAPTION.md and FIGURE_RECEIPT.json. The figure receipt initially awaits a separate actual visual check; a plotting failure preserves its partial output. Existing directories are refused, and no historical source or artifact is overwritten.

The plotted population is ALL_COMPLETE_NONEMPTY. The full experiments retain all 240 scenes; the 26 incomplete-reference and 11 strict-empty scenes have separate metrics. First-display-label cp applies the first label shown to that pipeline's finalized words; it is not partial-transcript WER, a known-person identification score, or actual display latency. Latest cp includes bounded retrospective attribution revisions. Shared scenes and O0/O1 views are dependent. B36 is the original cross-generation full-pipeline comparator, not an isolated algorithm control. Return, abstention, short-turn, naming and cost tradeoffs remain outside this two-metric view. No uncertainty interval, independent replication, dominance or final-selection claim is added.

Use the existing ANALYSIS interpreter with Matplotlib. No installation or environment change is needed.

## PowerShell

~~~powershell
$s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = "$s6cSim\reports\S6C\20260910T123540Z"
$s6cAnalysisPython = "$s6cSim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $s6cAnalysisPython -B "$s6cSim\scripts\s6c_plot_attribution_v1.py" --spec "$s6cReport\design\ATTRIBUTION_FIGURE_SPEC_V1.json" --spec-sha256 9751c25499da69e456b8bf62d148143d1eafffcf023749af0bf9d47bcbfc31e1 --output "$s6cReport\figures\attribution_tradeoffs_v1"
~~~

## Anaconda Prompt or Windows CMD

Use the full ANALYSIS executable even if another Conda environment is active.

~~~bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%S6C_SIM%\reports\S6C\20260910T123540Z"
set "S6C_ANALYSIS_PYTHON=%S6C_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%S6C_ANALYSIS_PYTHON%" -B "%S6C_SIM%\scripts\s6c_plot_attribution_v1.py" --spec "%S6C_REPORT%\design\ATTRIBUTION_FIGURE_SPEC_V1.json" --spec-sha256 9751c25499da69e456b8bf62d148143d1eafffcf023749af0bf9d47bcbfc31e1 --output "%S6C_REPORT%\figures\attribution_tradeoffs_v1"
~~~

After the first successful run, use a fresh output name for a reproduction. Visually inspect the PNG for counts, point/legend distinction, labels, clipping, shared axes and caption scope; retain the original figure receipt plus a separate source-bound visual review. A plot receipt by itself does not claim visual acceptance.

The explicit spec allows a later fresh version to add completed N08/N10/N12 or other admitted full-bank configurations without editing scores or silently discovering newer results. Create a new spec with exact completed receipts/tables, expected aggregate/source counts, fixed candidate order and both taps, then supply its exact hash and a new figure namespace. The 203/6,016 cohort remains fixed; a different population requires a separately reviewed plotting version. Dynamic row height and caption order support the expanded spec. Never overwrite the V1 specification, output or prior review. Keep later full native scoring/comparisons ahead of this optional reporting work; do not plot during a quiet paced resource interval.

