# Full N12 compact results

Purpose: summarize the completed C076 (N12 fixed endpoint-rule recipe) full-bank core results, matched C065 parent, and C067 mature-window comparator using exact completed tables. This is outcome-informed confirmation; no final operating choice is made.

Inputs: SHA-pinned C065, C067 and C076 ANALYSIS_RECEIPT files and their PROFILE, SCENE, SHORT_REPLY, TRACK_LIFECYCLE and RECIPE_COST tables; the fixed11-comparison scope; and an explicitly hashed completed comparison receipt. The source imports only the pinned old N03 compact table/numeric utilities. Its aggregation derives from the preserved reviewed N08/N10 summary, with the finite source, comparison and extreme-selection declarations changed. No scorer/native module, model, audio, prediction or raw-log read occurs.

Outputs: a fresh `reports/S6C/20260910T123540Z/full_n12_results_v1/RESULT.json` with source hashes, six complete profile/tap rows, every population, short evidence and censored waits, lifecycle/logged counts, nested observed/missing native costs, text/empty changes, all11 paired results and16 deterministic scene extremes. Existing outputs are never overwritten.

The fixed comparisons are C065/B00/B01/B36/C067 each O0 and O1 to C076, and C076 O0 to O1. Historical pairs compare whole generations. C067 versus C076 changes mature evidence and endpoint settings together. The exact comparison spec preserves the historical adapters and all240 case lists from the pinned earlier N03 spec while appending the completed C076 receipt. This is configuration construction only; no old score or source changes.

Use the existing ANALYSIS interpreter; no package installation. Run comparison only if its namespace does not yet exist, then the compact summary. Do not compete with a reserved quiet paced run.

PowerShell:

~~~powershell
$s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cSim 'staging\s5_text_metrics\analysis_env\Scripts\python.exe'
Set-Location -LiteralPath (Join-Path $s6cSim 'scripts')
& $s6cPython -B s6c_full_n12_summary_v1.py --test
& $s6cPython -B s6c_compare_v2.py --spec design/full_n12_compare_v2_inputs_V1.json --output-subdir full_n12_comparisons_v1
$s6cReceipt = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\full_n12_comparisons_v1\COMPARISON_RECEIPT.json'
$s6cSha = (Get-FileHash -LiteralPath $s6cReceipt -Algorithm SHA256).Hash.ToLower()
& $s6cPython -B s6c_full_n12_summary_v1.py --comparison-sha $s6cSha
~~~

Anaconda Prompt / Windows CMD:

~~~bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
cd /d "%S6C_SIM%\scripts"
"%S6C_PYTHON%" -B s6c_full_n12_summary_v1.py --test
"%S6C_PYTHON%" -B s6c_compare_v2.py --spec design/full_n12_compare_v2_inputs_V1.json --output-subdir full_n12_comparisons_v1
"%S6C_PYTHON%" -B -c "import hashlib,pathlib,subprocess,sys; p=pathlib.Path('../reports/S6C/20260910T123540Z/full_n12_comparisons_v1/COMPARISON_RECEIPT.json'); subprocess.run([sys.executable,'-B','s6c_full_n12_summary_v1.py','--comparison-sha',hashlib.sha256(p.read_bytes()).hexdigest()],check=True)"
~~~

Complete-reference headlines cover203 scenes/6016 words/693 turns/292 returns per route. Word errors combine156 primary serialized-WER scenes/4560 words with47 complete-overlap MIMO scenes/1456 words; this is not one serialized raw-word alignment. Incomplete26 and strict-empty11 remain separate. Empty-reference insertion counts have no WER denominator. The input bank has nonuniform durations; retain actual source durations.

First-display-label cp uses finalized words with the first-displayed labels; it is neither partial-word WER nor actual wall-time display latency. Latest cp includes bounded attribution revisions. Changed words mean cp differences cannot be attributed solely to tracking. Primary-word2000-resample uncertainty is distinct from point cp changes.

Subsecond40 and1-to-under2-second34 populations retain evidence, known support, mapped correctness and observed/censored waits separately. Lifecycle sums combine fresh scenes, not continuous state. Native model/API/full-dispatch costs are nested and overlapping; do not add them as total wall time. Execution batches/reuse and accelerated timing limit runtime interpretations.

For C076 versus C065, each tap and word/latest-cp metric retains the two largest and two smallest signed scene-rate changes, ties by case ID. Zero changes are ties, not harms/benefits. These are descriptive extremes, not typical examples or selection criteria. Source receipts, settings and prior outputs remain unchanged.

