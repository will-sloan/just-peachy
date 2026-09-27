# Main aggregate comparison figure

Purpose: plot primary WER by ASR/tap and pooled cpWER for all 16 compositions.
Inputs are the accepted main-scoring receipt and its hash-verified private report.
Output is a fresh PNG using the existing Anaconda matplotlib installation and
the noninteractive Agg renderer. Primary WER equality across D/E variants is
checked, and cpWER is pooled by summing edits and words, not averaging rates.
Only aggregate values are drawn. No private captions, voices, profiles or room
identifiers are copied. Model inference, GUI windows, device access and Pi
connections are not used. CPU14/BelowNormal, one math thread and GPU-off settings
are applied before importing the plot library. Existing outputs are preserved.

The figure is descriptive modeled evidence; it is not a naming, GUI, resource,
CM5 or N4/N5 acceptance claim. Its companion MAIN_MODELED_RESULTS_V1.md provides
denominators, metric support and paired comparison exclusions.

PowerShell in an existing shell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$plotPython='C:\Users\amiri\anaconda3\python.exe'
$stage='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $plotPython -B "$stage\plot_main_scores_v2.py" --acceptance "$stage\MAIN_MODELED_SCORING_ACCEPTANCE_V1.json" --output "$stage\MAIN_MODELED_RESULTS_V2.png"
```

CMD or Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PLOT_PY=C:\Users\amiri\anaconda3\python.exe"
set "JP_STAGE=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%PLOT_PY%" -B "%JP_STAGE%\plot_main_scores_v2.py" --acceptance "%JP_STAGE%\MAIN_MODELED_SCORING_ACCEPTANCE_V1.json" --output "%JP_STAGE%\MAIN_MODELED_RESULTS_V2.png"
```

No installation or environment changes are needed. For reproduction, choose a
new output filename and visually check labels/captions before sharing the PNG.

V1 source and its initial PNG are preserved in the private plot-v1 audit. Visual
review found the lower-right legend overlapping A3; V2 only moves the legend.
The numerical inputs and bar values are unchanged.
