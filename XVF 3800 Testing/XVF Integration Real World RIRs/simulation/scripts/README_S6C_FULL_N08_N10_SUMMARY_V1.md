# Full N08/N10 compact results and fixed comparisons

This helper summarizes completed C072 (N08 hard-argmax segmentation post-processing) and C074 (N10 two-path modified-beam ASR decoding) full-bank core results against C065 (N01). It validates and aggregates exact completed compact tables. It does not import a scorer, read original predictions/native logs/audio, run policy replay, or execute models.

Inputs are the SHA-pinned full N01 anonymous and full N08/N10 core receipts, their bound PROFILE/SCENE/SHORT_REPLY/TRACK_LIFECYCLE/RECIPE_COST tables, the fixed18-comparison scope, and the completed comparison receipt selected by an explicit SHA argument. It imports only the exact held s6c_full_n03_summary_v1.py table/numeric utilities after verifying that source's SHA. The earlier N03 helper and all old outputs remain unchanged.

Outputs are reports/S6C/20260910T123540Z/full_n08_n10_results_v1/RESULT.json, with all source bindings, complete-population arithmetic checks, all population rows, short-turn support and observed/censored waits, lifecycle/logged activation counters, observed/missing nested native costs, word-text changes, strict-empty insertions, full matched comparisons, primary-word conditional uncertainty, and deterministic case extremes. It refuses an existing output namespace. Reproduction after the original run requires a separately versioned helper/output, not deletion or overwrite of completed evidence.

The 18 comparisons were fixed before inspecting full score outcomes: each of C072/C074 versus C065/B00/B01/B36 on O0 and O1, plus each candidate's fixed O0-to-O1 contrast. Historical controls are whole-pipeline, cross-generation comparisons. Scope is outcome-informed full confirmation, not untouched holdout. The scope records an initial shell-only construction failure before publication (reserved PID variable); no scientific data was changed.

## PowerShell

Use the pinned ANALYSIS interpreter. First execute only the five tiny numeric/selection guards. The completed comparison spec already binds all240 scenes and authoritative score receipts. Run the comparison command only if its output does not yet exist; do not rerun completed comparisons.

~~~powershell
$s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cAnalysisPython = "$s6cSim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
Set-Location -LiteralPath "$s6cSim\scripts"
& $s6cAnalysisPython -B s6c_full_n08_n10_summary_v1.py --test
& $s6cAnalysisPython -B s6c_compare_v2.py --spec design/full_n08_n10_compare_v2_inputs_V1.json --output-subdir full_n08_n10_comparisons_v1
$s6cComparisonReceipt = "$s6cSim\reports\S6C\20260910T123540Z\full_n08_n10_comparisons_v1\COMPARISON_RECEIPT.json"
$s6cComparisonSha = (Get-FileHash -LiteralPath $s6cComparisonReceipt -Algorithm SHA256).Hash.ToLower()
& $s6cAnalysisPython -B s6c_full_n08_n10_summary_v1.py --comparison-sha $s6cComparisonSha
~~~

## Anaconda Prompt or Windows CMD

These commands explicitly use ANALYSIS, regardless of the active Conda environment. The final command asks the same pinned interpreter to compute the SHA of the existing completed comparison receipt and invoke the summary as a separate process; it never executes a shell-built command string.

~~~bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_ANALYSIS_PYTHON=%S6C_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
cd /d "%S6C_SIM%\scripts"
"%S6C_ANALYSIS_PYTHON%" -B s6c_full_n08_n10_summary_v1.py --test
"%S6C_ANALYSIS_PYTHON%" -B s6c_compare_v2.py --spec design/full_n08_n10_compare_v2_inputs_V1.json --output-subdir full_n08_n10_comparisons_v1
"%S6C_ANALYSIS_PYTHON%" -B -c "import hashlib,pathlib,subprocess,sys; p=pathlib.Path('../reports/S6C/20260910T123540Z/full_n08_n10_comparisons_v1/COMPARISON_RECEIPT.json'); subprocess.run([sys.executable,'-B','s6c_full_n08_n10_summary_v1.py','--comparison-sha',hashlib.sha256(p.read_bytes()).hexdigest()],check=True)"
~~~

## Denominators and limits

The complete-reference headline has203 scenes/6016 words/693 source turns/292 return groups per route. Incomplete26 and strict-empty11 scenes remain separate. The full input bank has nonuniform durations; each source row retains its actual duration. Subsecond and1-to-under2-second short-turn populations are40 and34; evidence containment, known support, duration-mapped correctness and censored waits remain different quantities.

First-display-label cp uses finalized words with the first-displayed label. It is not partial-transcript WER or actual source-paced display latency. cp includes word and anonymous attribution error; changed decoder words prevent attributing all cp change to tracking. The unchanged comparison engine supplies point cp deltas and separate2000-resample conditional primary-word intervals; it does not supply cp confidence intervals.

Native model/API/full-dispatch costs are nested and overlap. They cannot be summed as whole-pipeline elapsed time. Original native execution spans reused panel cells and new batches. These table-derived costs and logged activation counts do not establish source-paced latency, hardware deployment performance or unlogged branch activation.

Extremes follow the fixed scope: for each candidate/tap and latest-cp/raw-word metric, retain two largest signed harms and benefits divided by that scene's reference count, ties by case ID. These are descriptive maxima, not typical cases or an operating-selection rule. The helper preserves all complete tables and every declared comparison rather than filtering to favorable cases.

No final configuration retention, new setting, new model call or automatic operating recommendation is made by this code.

