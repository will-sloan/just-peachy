# S6B scientific figures

Purpose: render four readable, exportable result figures from completed full-bank score tables: primary words/attribution, unknown/mixed identity, all40 short replies, and return consistency. It performs no model inference or statistical refitting.

Inputs: `PROFILE_RESULTS.csv`, `SHORT_REPLY_RESULTS.csv` and `ANALYSIS_RECEIPT.json` in the selected S6B score directory. Every plotted profile must have all240 scenes on both taps and all40 subsecond references. Outputs: four PNGs, four matching SVGs, captions and a source/code hash manifest in a fresh output directory. PNG/SVG pairs are two formats of four figures, not eight analyses. Open the PNGs for visual inspection before packaging.

PowerShell (replace profile IDs/analysis directory with the completed shortlist ledger values):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6b_plots.py" --analysis-subdir full_analysis_v1 --profiles B00 B36 B01 --output-subdir figures_v1
```

Anaconda Prompt or Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6b_plots.py" --analysis-subdir full_analysis_v1 --profiles B00 B36 B01 --output-subdir figures_v1
```

The existing Anaconda NumPy/Matplotlib packages suffice. Use a fresh figure directory after any change; prior renders are preserved. The figures name metric populations/denominators and distinguish contained evidence, label presence and mapped correctness. All underlying counts and missing/tied cases remain in the score tables.
