# S5 final scientific figures

`s5_figures.py` creates exactly four Matplotlib figures and exports every plotted numeric value, count and denominator to `plotdata.csv`. It reads completed development aggregate results only. It does not launch models, open raw audio/native task logs, control hardware, fit thresholds or score protected reserve scenes.

Inputs come from `simulation/reports/S5/20260909T130308Z`: `SUMMARY_METRICS.json`, `PAIRED_METRICS.json`, `SHORT_TURN_SUMMARY.csv`, the frozen protocol/job manifest and the optional completed `representation/SUMMARY_COMPACT.json`. The final loader requires `COMPLETE_PANEL`,180 unique development scene pairs,360 completed/analyzed outputs and zero reserve evaluations. It checks the exact frozen job allowlist and protocol binding. A partial integration summary is refused before per-scene performance aggregates are opened.

Outputs are four150-dpi PNGs, `plotdata.csv`, `CAPTIONS.md` and `FIGURE_RECEIPT.json` under the report's `figures` directory. The receipt records source/code hashes, image size, exported data, font size, layout checks and the absence of raw native/audio access. All fonts are at least9points. PNGs are suitable for the compact handoff; raw vectors/logs/audio remain local. The script creates no additional figure beyond these four.

## Run in PowerShell

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
# Safe layout test: synthetic values only, written to staging/s5_figures_preview.
& 'C:\Users\amiri\anaconda3\python.exe' s5_figures.py --preview-fixtures
# Run only after the coordinator confirms final COMPLETE_PANEL.
& 'C:\Users\amiri\anaconda3\python.exe' s5_figures.py
```

## Run in Anaconda Prompt or Windows command line

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s5_figures.py --preview-fixtures
"C:\Users\amiri\anaconda3\python.exe" s5_figures.py
```

Use the existing Anaconda NumPy/Matplotlib installation. No dependency installation is needed. Rendering is serial and creates no model/worker pool. Re-run the same command after approved final aggregate changes; the final receipt binds the actual consumed aggregates. Do not rename or copy synthetic previews into the final report: previews carry conspicuous `SYNTHETIC FIXTURE` titles and their receipt status is `SYNTHETIC_PREVIEW_ONLY`.

## Figures and scientific boundaries

1. `01_words_and_paired_scenes.png`: pooled primary non-overlap WER and separate overlap MIMO-WER with errors/reference words; paired primary scene scatter. The populations are distinct. Points share sources/rooms and are not independent trials.
2. `02_primary_condition_differences.png`: descriptive O1-minus-O0 primary WER differences by four rooms, corpus/quality and all12 families. MIXED categories remain mixed. Missing primary-family cells show unavailable withn=0. Only the overall conditional matched-block95% interval is drawn; individual condition points have no invented confidence intervals. Grey±1-point shading is the frozen planning reference, not a validated product requirement or equivalence result.
3. `03_attribution_returns_and_short_turns.png`: primary/overlap final-label cpWER; primary repeated-participant groups and their after-other-speaker subset with consistent/inconsistent/unknown retained; supported native speech flags in whole-clip and estimated-active bins. Only `single_source_attributable` rows contribute flag percentages, and counts explicitly use observed turns. This is not short-reply recognition, timed-overlap recall, enrolled identity or DER.
4. `04_evidence_headroom_and_oracle.png`: successful embedding calls per decoded minute; unique evidence-audio duration versus summed overlapping windows; raw PCM24 headroom and rail counts; completed oracle-window cosine medians andp10–p90 intervals when available. Quantile lines are distributions, not CIs. Oracle windows are source-selected and dependent; no threshold or online identity claim follows.

O0 is the existing recorded ASR output with fixed+3dB host gain; O1 is the recorded postprocessed auto output at unity. Headroom/rail annotations use raw preadapter PCM24 and retain the packed-payload positive rail criterion. No processing is applied by this figure script. Missing mapping, unknown ambient references and incomplete native gate observability remain limitations from the input summaries. Seven music-only controls lack saved output lag: the source/shared-noise window repair covers39 cases, while output-local mapped real-noise diagnostics cover32; do not imply complete39-case output-local coverage from these figures.

After rendering, visually inspect all four PNGs. Automatic text-bound checks flag content extending beyond the canvas, but human visual review is still needed for crowded labels. The script returns a nonzero status if it detects such a boundary warning. Plotted CSV rows identify figure/panel/group/output/metric/value and retain applicable numerator, denominator, sample count and unit; scatter rows retain both output coordinates and word counts.

The synthetic preview was executed and all four layouts were visually inspected. Crowded fraction/count labels and cross-panel rail labels were corrected before delivery. The final-only guard was separately verified to reject `PARTIAL_DIAGNOSTIC`. The first completed-panel render revealed an automatic oracle-axis tick outside the canvas; a display-only tick locator prunes endpoint ticks without altering plotted values or limits. Its original code, README and receipt are retained in `staging/s5_figures_final_layout_attempt1`. Final PNGs must be visually checked after rendering; `FIGURE_RECEIPT.json` records the current result and exact consumed inputs.
