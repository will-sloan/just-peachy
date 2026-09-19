# Component figures

`s6a_probe_figures.py` creates two standalone PNG figures and their exact CSV plot data from the completed `COMPONENT_PROBE_SUMMARY.json`. It fails if the full 720 native comparisons are not scored. No model, audio, true identity or new scoring is involved. The plots show paired-screening lexical outcomes (23 primary and29 complete-reference scenes per tap) and instrumented model-call elapsed sums; they do not certify CM5 speed or a winning production profile.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_probe_figures.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s6a_probe_figures.py
```

Outputs are in `simulation\reports\S6A\20260909T202250Z\figures`: two `S6A_COMPONENT_*.png` files, `S6A_COMPONENT_PLOT_DATA.csv` and `PROBE_FIGURES_RECEIPT.json`. Visually inspect both PNGs before packaging; re-running deterministically replaces only these derived artifacts. ASR stacks include tail dispatch and EOF drain. Model loading, wrapper/postprocessing, tracker/gate, advisory/reset, formatting and process overhead are not fully included. Segmentation timing ends before powerset-posterior conversion. Concurrency also prevents treating these incomplete sums as serial wall time or steady-state real-time factor. Fresh-process model loading is not necessarily uncached storage or cold-boot loading.
