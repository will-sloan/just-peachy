# Five saved metric timeout retests

## Purpose

`retest_metric_timeouts_v1.py` evaluates only the five TIMEOUT rows from the
closed 7,680-case V3 main scoring run. That run produced 7,675 SCORED rows and
five TIMEOUT rows at a 60-second per-request limit. The supervisor exited zero,
but the terminal correctly reports PARTIAL_MODELED_BANK_SCORING. Its automatic
review handoff stopped without dispatching because complete scores are required.

The existing qualified `MetricProcess` and production scorer both support up
to 120 seconds per request. This bounded diagnostic uses that existing limit
and exactly the same metric code, environment, truth, predictions and model
outputs. It changes no model, threshold, metric, alignment or reference. It
does not re-infer audio, overwrite failed rows or merge results into the old
bank. A passed five-case retest is not a complete reviewed scoring bank.

## Inputs and outputs

Input is the exact `local/n4/integrated-main-scores-v3` terminal/admission and
all 7,680 score bindings, with missing indices 00888, 00889, 01417, 01424 and
06568. All original metric owners/pipe threads and the original scorer must
have exited. The frozen main method bank, matching passed method review,
complete artifact histories, evaluator-only truth and pinned metric environment
are independently checked through the already-qualified V3 admission/conversion
and row-validation functions. No predictor is imported into the evaluator.

Output in a fresh private directory is ADMISSION, up to five new cell scores,
preserved failed-cell receipts and RESULT or FAILED. Each successful score binds
its old failure, unchanged method result and reconstructed metric input digest.
All five metric requests have exact process/pipe closure evidence. Actual code,
references, audio, hypotheses and metric data remain private as appropriate;
only source and small count/hash reports go to Git.

The process uses the existing metric writer lock, CPU14/BelowNormal, one math
thread and GPU off. Limits: 120 seconds per request, 20 minutes checked between
operations, 8 MiB output, the existing six-GiB shared reservation policy plus
contingency, C:50/G:75-GiB floors and the original packaging cutoff. It starts
no GUI, device, microphone, playback, training, enrollment or Pi connection.

## PowerShell

Use an existing shell and fresh output. For campaign dispatch use the existing
supervisor and hidden process interface; never start a duplicate metric worker.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$metricPython='G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
$stage='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $metricPython -B "$stage\retest_metric_timeouts_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\main-metric-timeout-retest-v1'
```

## CMD and Anaconda Prompt

Use the pinned interpreter without modifying or activating another environment:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "METRIC_PY=G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe"
set "N4_STAGE=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%METRIC_PY%" -B "%N4_STAGE%\retest_metric_timeouts_v1.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\main-metric-timeout-retest-v1
```

Both commands refuse an existing output. Preserve failures and investigate
them; do not keep raising limits or modify the running source. This is an
actual saved-input metric check, not a mock test. Successful results still need
a complete bank and independent review before downstream admission. An unchanged
full scorer run with `--cell-timeout 120` is an existing supported option after
this diagnostic and all exact owners close, if the evidence justifies it and
fresh resource admission passes. It reuses all frozen method predictions and
does not require new ASR/diarization/embedding inference. Its output must also
be fresh; the old partial bank and failed automatic handoff remain immutable.
