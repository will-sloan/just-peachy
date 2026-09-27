# Component performance report and measurement summary

Purpose: explain the measured accuracy and processing cost of the N2/N3/N4
components, especially Nemotron-3 diarization. Read
`COMPONENT_PERFORMANCE_REPORT_20260927.md` for the report. This documentation
does not promote an N4 release or claim completed N5 acceptance.

`summarize_d1_processing_v1.py` reads existing receipts and compressed events;
it does not load models, perform inference, access devices or modify inputs.
It verifies all 960 cell/result/event bindings against the independently
reviewed D1 bank and reports aggregate measurements only. No audio, transcripts,
speaker vectors or personal data are included in its output.

Inputs: the public `n4/D1_FULL_BANK_REVIEW_V3.json` (default), its bound private
review and the local files referenced by that review. They must exist at their
recorded paths. Requires Python 3.10+ standard library. Commands below also use
the existing environment's psutil to constrain this read-only report pass to
CPU14 at BelowNormal priority, within campaign limits.

Output: a **new** JSON file specified by `--output`; the parent must exist.
Existing output is refused. Committed `D1_PROCESSING_SUMMARY_V1.json` is the
verified report input; choose another filename when reproducing. Processing
may take about a minute because every compressed event file is verified/read.
Errors return a nonzero exit without issuing a success report.

PowerShell, from the campaign worktree:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$perfPy = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$perfScript = 'research\nvidia_nemo_comparison\20260924_campaign\n5\summarize_d1_processing_v1.py'
& $perfPy -B -c "import psutil,runpy,sys; p=psutil.Process(); p.cpu_affinity([14]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" $perfScript --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-processing-summary-recheck.json'
```

Command Prompt or Anaconda Prompt (no activation/install needed):

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree"
set "PERF_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PERF_SCRIPT=research\nvidia_nemo_comparison\20260924_campaign\n5\summarize_d1_processing_v1.py"
"%PERF_PY%" -B -c "import psutil,runpy,sys; p=psutil.Process(); p.cpu_affinity([14]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%PERF_SCRIPT%" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-processing-summary-recheck.json"
```

The report uses summed errors / summed reference words, summed collection time /
summed audio duration, and `(actual_finished_elapsed_sec - actual_started_elapsed_sec)`
from each actual dispatch/embedding event. Reported RSS is the largest recorded
post-cell sample, not an independently measured peak. The simulated availability
clock is never used as observed latency. N2 CUDA resources and N3 ASR resources
come from their existing reviewed summaries, as linked in the report. No new
neural evaluation is needed to reproduce this report.
