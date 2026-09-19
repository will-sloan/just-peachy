# S4.5 compact metrics and scientific plots

`s45_results.py` aggregates existing, verified S4.5 evidence into `summary_metrics.json`, a 240-row `per_scene_metrics.csv`, and at most four PNG figures with one combined `plots\plotted_data.csv`. It runs no models, reads no audio/model payload, opens no hardware and never reads reserve task results. It reads JSON receipts and hashes the referenced analysis/event metadata files. New figures summarize available evidence; pending work is not given fabricated scores.

Run `s45_coverage.py` first so its compact coverage exports reflect current capture progress. Required inputs are the frozen `scene_bank\s45_v2_20260909T031300Z\SCENE_MANIFEST.json` (current `BANK` in `s45_common.py`) and `reports\S4_5\20260909T031300Z\COVERAGE_SUMMARY.json`. The unused v1 bank and initial exports were archived before hardware/H2 execution after an F09 input-energy-window correction; source/split roles remain unchanged. The aggregator then reads any available authoritative canonical/reference acceptance manifests, `CAPTURE_ANALYSIS.json`, `REFERENCE_CAPTURE_ANALYSIS.json`, per-case audio/spatial metadata, predeclared sentinel/dry plans, and H2 job receipts/metrics. Output jobs are restricted to the 24 predeclared development scenes, O0/O1. Dry jobs are restricted to the separately frozen development-source control plan, at most 24. Unexpected job paths are rejected before opening their contents.

Every completed H2 result must have an exact job/contract/input/gain identity, native completed session summary, zero exit status, no stale error, bound metrics/events, and full-input completion evidence. Derived/reconstructed S4.5 summaries are rejected. A grossly saturated output can have a zero-invocation `QUARANTINED` receipt with no score denominator. Failed, in-progress, quarantined and never-started jobs remain separate from native completed jobs; they cannot silently become zero-error observations.

`summary_metrics.json` reports intended 240/180/60 versus accepted/analyzed counts; exact native/decoded/compared sample totals and differences; raw rail counts/runs and level gates by output/split; development-only causal spatial support, acquisition censoring, receipt health and return limitations; valid nonoverlap raw WER/CER edit counts and denominators by output/corpus/documented quality; a separate common O0/O1 eligible-case pool; strict nonspeech/silence false words; available embedding-window and anonymous-label continuity evidence; and dry-source context comparisons. False-word rates retain the scorer's native decoded H2 input duration from completed session telemetry, not intended canonical duration. All consumed metadata bindings are retained. Full transcripts remain in the local scorer artifacts and are omitted from this compact summary.

Mixed native-quality HiFi scenes have their own combined quality category. Their entire-scene reference denominator is counted once; it is not attributed in full to each constituent quality category. Ordinary WER excludes scheduled overlap and uncertain/untranscribed ambient speech. Target-only ambient scores are not pooled. A single source's dry WER is not subtracted from a multi-turn processed scene's WER. A descriptive difference is allowed only when the processed scene contains exactly that single whole source clip with a complete, nonoverlapping reference; even then the acoustic/level/device chain is a composite condition, not an isolated causal effect.

Reserve cases contribute only coverage, sample integrity and output levels. Their spatial task pointers are rejected before metrics are opened; no reference-matched direction, text, H2, embedding or name score is computed. Optional naming-reference captures are level-only and remain separate from the 240 cases. Preparation or capture does not execute enrollment. A missing aligned speaker-turn evidence field remains unavailable, rather than perfect continuity. Host receipt gaps and identical values are not proof of stale internal DSP. All figures exclude reserve task scores and population confidence intervals. No final output winner, full DER, naming accuracy, age/accent causal claim or fusion benefit is declared.

Within `embedding_evidence.by_output`, `decision_label_fragmentation` summarizes successful anonymous embedding decisions, while `emitted_final_label_fragmentation` summarizes the speaker labels actually written on final transcript events. Each reports supported/missing jobs, observations, the sum of within-job distinct-label counts, within-job switches and jobs with multiple labels. `label_evidence_by_job` retains compact count/switch pairs for each case without transcript text. Anonymous label strings restart in each fresh H2 job: the sum of per-job distinct labels is not a unique-person count, and switches between different jobs are never counted. A switch can also represent a correct speaker change; it is not automatically a fragmentation error.

The existing source-matched reference-turn and returning-participant fields remain separate. They use fully contained single-source file-support embedding windows, including eligible exclusive portions of overlap scenes. All-speaker overlap WER remains LIMITED. A returning-participant group requires complete dominant-label evidence across that participant's scheduled turns; ties or missing evidence remain unknown. These descriptive continuity groups can include repeated isolated turns and are not enrolled-person accuracy.

`reconciled_cluster_lineage` retains the per-job reconciliation status and leaves `underlying_cluster_fragmentation` null. The unchanged edge baseline explicitly reports `UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE`: observed decision labels and concurrent final-transcript snapshots do not reconstruct unlogged cluster merges or retrospective lineage. Missing label fields remain unavailable; an explicitly recorded empty label list is observed zero, not missing metadata or perfect continuity. Decision counts and emitted-final lists are checked against the existing successful-call count and final transcript records.

A read-only spatial review of the frozen v2 schedules and the first six completed F01 analyses found no current case affected by updating the seen-participant set after limited-turn exclusion. The frozen scorer applies overlap status to the entire scene, and ambient reference completeness is scene-wide. Those six analyzed scenes contained 18 valid turns and 12 later-participant turns per stream; their summed and unioned support durations agreed. This was a partial audit snapshot, not a claim about final campaign outcomes. No spatial scorer or return-selection logic was changed by the reporting fix.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_results
& 'C:\Users\amiri\anaconda3\python.exe' s45_coverage.py
& 'C:\Users\amiri\anaconda3\python.exe' s45_results.py --validate-only
& 'C:\Users\amiri\anaconda3\python.exe' s45_results.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_results
"C:\Users\amiri\anaconda3\python.exe" s45_coverage.py
"C:\Users\amiri\anaconda3\python.exe" s45_results.py --validate-only
"C:\Users\amiri\anaconda3\python.exe" s45_results.py
```

Use `s45_results.py --no-plots` for metrics only. `--validate-only` writes nothing and does not import Matplotlib. Missing required inputs produce `PENDING_REQUIRED_INPUTS`, no output writes and exit 2. Invalid identities, hashes or eligibility produce exit 1. Valid partial evidence produces `PARTIAL_EVIDENCE` and exit 0. `COMPLETE_WITH_LIMITATIONS` requires all 240 accepted/audio-analyzed captures, all 180 development spatial cases, all 48 output jobs either native completed or explicitly quarantined, and all planned dry controls native complete. Optional references retain their independent accepted/analyzed counts. The output status is an evidence-accounting state, not a performance pass or permission to train.

Plots use installed Matplotlib with the noninteractive Agg backend. No installation or download is attempted. The four potential plots are: capture coverage/raw rails; development spatial support (only when spatial evidence exists); nonoverlap ASR raw-count evidence (only when eligible scores exist); and H2 job/embedding evidence. `plots\FIGURE_INDEX.json` binds each generated PNG, combined numeric CSV, summary and code, and leaves visual QA explicitly pending. The coordinator should inspect the final figures and record QA before final packaging. Plot files are regenerated from current metrics; the index is the authoritative list and is limited to four figures.

Offline fixtures cover reserve gates before task-file access, independent edit/denominator checks, LIMITED/empty-reference handling, mixed-quality accounting, raw transport sample counts and silent alignment, weighted spatial support/censoring, unavailable embedding evidence, unpaired dry comparisons and rejection of derived summaries. A temporary fixture also renders all four plots and checks the combined numeric CSV without writing fabricated final artifacts. Tests use no actual audio, hardware or models.

Additional reporting fixtures distinguish decision labels from emitted final labels, preserve independent job namespaces, distinguish missing evidence from an empty observed list, and reject count/list inconsistencies. All 17 results tests passed on 2026-09-09 in 2.420 seconds, including the temporary four-plot export. The result was observed through the command tool; no separate stdout artifact was retained. The prior report code, test file and README plus the exact reporting diff and validation receipt are preserved under `simulation/staging/s45_results_review/v1`. This change adds report fields without changing existing metric keys, the frozen execution/scoring code, thresholds, models, timing alignment or scientific policy.


## Final visual review, 2026-09-09

After the supervisor closed, tool inspection found legends covering part of the accepted-count and spatial bars. A layout-only revision makes the first legend one row and moves the spatial legend to empty upper-left space. It changes no input, metric, denominator, scientific setting or other function. Prior code, README, complete metrics and four plots are retained under staging/s45_results_review/v2_plot_layout/original; LAYOUT_RECEIPT.json and plot_layout.patch bind the change. Re-run the same documented s45_results.py command to regenerate report artifacts, then inspect all four PNGs before marking visual QA. No model or hardware run is required.
