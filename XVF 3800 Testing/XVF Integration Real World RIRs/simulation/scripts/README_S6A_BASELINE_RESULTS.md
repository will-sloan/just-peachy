# S6A all-240 baseline analysis

Purpose: aggregate the 480 existing original-settings O0/O1 S6A metric results into count-based text, support, continuity, level, dependency, geometry and desktop-cost evidence. The script runs **no inference** and opens no audio, model or embedding payload. It never changes canonical RIRs, bank metadata, source flags, app code or older S5 evidence.

Inputs: the fixed all-240 SCENE_MANIFEST.json, canonical RIR_MANIFEST.json, S6A JOB_MANIFEST.json, BASELINE_SCORE_RECEIPT.json, bound baseline_metrics results and small native wrapper receipts. Both COMPLETE and COMPLETE_REUSED_SCORE rows are accepted only after their result hash and native completion contract validate. Hash mismatches fail. The historical 180/60 split is retained for descriptive analysis; S6A authorizes all240, and the former60 is not labeled unseen holdout.

Outputs: REPORT/baseline_results/BASELINE_ANALYSIS.md, BASELINE_RESULTS.json, SUPPORT_RESULTS.json, compact per-scene counts, coverage/strata/cost/short-turn/return/region CSVs, RIR_GEOMETRY_AUDIT.json, DEPENDENCY_PLAN.json, PAIRED_UNCERTAINTY.json, fixture and binding receipts. Optional one scientific PNG has its plotted values in FIGURE_DATA.json.

Use the existing Anaconda Python with NumPy and optional Matplotlib already installed. No installation or environment change is needed. Work is serial (one analysis process). Pure aggregation helpers are reused from s5_results.py/s5_statistics.py; their S5-only run functions and guard are never called. The S6A script implements full-240 dependencies and dynamically reports five rooms. A missing primary pair drops its entire requested primary matched block from conditional resampling and remains explicit in coverage. Every requested output has a coverage row.

PowerShell, metadata and meaningful fixture checks while scoring is in progress:

~~~powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs'
& 'C:\Users\amiri\anaconda3\python.exe' '.\simulation\scripts\s6a_baseline_results.py' --report '.\simulation\reports\S6A\20260909T202250Z' --prepare-only
~~~

PowerShell, final aggregation only after the scoring receipt says COMPLETE and complete=480:

~~~powershell
& 'C:\Users\amiri\anaconda3\python.exe' '.\simulation\scripts\s6a_baseline_results.py' --report '.\simulation\reports\S6A\20260909T202250Z' --require-complete --plots
~~~

Anaconda Prompt or Command Prompt, equivalent commands:

~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs"
"C:\Users\amiri\anaconda3\python.exe" "simulation\scripts\s6a_baseline_results.py" --report "simulation\reports\S6A\20260909T202250Z" --prepare-only
"C:\Users\amiri\anaconda3\python.exe" "simulation\scripts\s6a_baseline_results.py" --report "simulation\reports\S6A\20260909T202250Z" --require-complete --plots
~~~

Optional diagnostic use: replace --require-complete with --allow-partial. Outputs are explicitly PARTIAL_DIAGNOSTIC and include missing/pending/failed jobs; do not present them as final. A receipt changing during aggregation fails its closing hash check. Repeat after root scoring is idle; don't concurrently overwrite metrics. --prepare-only reads zero task metrics and creates only metadata, dependency and fixture outputs.

Metrics: primary WER/CER pool edit counts; overlap uses MIMO-WER, final-label cpWER is diagnostic, incomplete ambient speech stays target-only limited, and strict-empty references use inserted words/minute with undefined WER. Uncomputed character counts for MIMO/cpWER remain null, with zero character-scored scenes. The 2,000 seeded whole-matched-block replicates are conditional within observed rooms; shared people/text/RIR/noise invalidate an independence claim. Equal-room, leave-room-out and dependency component deletions are descriptive sensitivities. Short-turn flags and identity label consistency are source-support proxies, not verified recognition. Desktop process timings include startup and prior host contention and cannot establish CM5 throughput.

The geometry audit confirms canonical versus selected metadata, PASS/REVIEW acquisition status, 120 eligible of121 records, the 39 used RIR projections, effective distances ≤5m, and preserved user-confirmed 100cm corrections. It does not redo waveform validation or independently calibrate angle signs. New code changes must update this README.

Fixture coverage: paired error count pooling, an incomplete member excluding its whole primary matched block, folded 0/90/180 native endpoints, and empty-reference insertion rate without WER.
