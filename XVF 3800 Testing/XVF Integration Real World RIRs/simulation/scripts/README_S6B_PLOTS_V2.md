# S6B scientific figures, layout revision 2

Purpose: render the same four source-bound S6B scientific figures with the first figure's tap legend below the axes so it does not overlap the bars. The previous script and figures are preserved. This changes only presentation, not source selection, metrics, inference or scoring. The only executable change from `s6b_plots.py` is that legend placement; its module docstring names this README.

Inputs: completed `PROFILE_RESULTS.csv`, `SHORT_REPLY_RESULTS.csv` and `ANALYSIS_RECEIPT.json` under the supplied analysis directory. Every plotted profile must contain all 240 scenes on both taps and all 40 short turns. Outputs: four PNG/SVG pairs, captions and a source/code manifest in a fresh directory. Open all four PNGs for visual QA. Eight files are two formats of four figures.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6b_plots_v2.py" --analysis-subdir full_analysis_v1 --profiles B00 B36 B10 B17 B25 B28 B37 B38 --output-subdir figures_v2
```

Anaconda Prompt or Command Prompt (no environment installation or activation needed):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6b_plots_v2.py" --analysis-subdir full_analysis_v1 --profiles B00 B36 B10 B17 B25 B28 B37 B38 --output-subdir figures_v2
```

Use another fresh output directory if deliberately rerendering; existing figures are never overwritten. The code/documentation index for 36 prior entries remains unchanged and source-valid. `FIGURE_LAYOUT_V2_RECEIPT.json` separately binds this additional script/README, the preserved source and final figure manifest, bringing documented code entries to 37. See the original `README_S6B_PLOTS.md` for shared metric scope. This version has no active-run dependency on the application or neural models.
