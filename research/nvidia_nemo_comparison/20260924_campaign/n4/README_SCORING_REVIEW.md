# Review of sealed modeled scoring banks

Purpose: `review_scoring_bank.py` checks the integrity of a complete modeled
scoring bank before its reports can support candidate selection. It requires
the original full 7,680-cell main or 1,536-cell additional-mode plan, complete
reviewed predictions, exact stopped driver/metric process identities, drained
metric pipes, request counts, and unchanged source, evaluator and metric code.
It imports no application or model runtime and starts no audio, GUI or scorer.

Inputs: a closed scoring run's RESULT/ADMISSION, sealed scores and REPORT;
its matching reviewed method bank and compressed publication/Controller outputs;
the frozen 480-job evaluator truth, 240-scene strata and original pinned metric
environment. Every metric input digest is reconstructed from the unchanged
conversion and reference. Word/error counts, class-specific metric availability,
formatting diagnostics, constant-speaker controls and estimated activity counts
are checked. The complete count-weighted/stratified and paired bootstrap report
is recomputed using the original report implementation.

This verifies inputs, internal metric algebra and report aggregation. It does
not rerun the optimal WER/cpWER/MIMO alignments or activity scorers, independently
validate references, establish recognition/naming accuracy, or demonstrate
actual widget timing, whole-application resources or deployment acceptance.
Partial results remain useful diagnostics but cannot pass this complete review.
No metric-unavailable value is replaced with zero.

Outputs: private ADMISSION.json followed by RESULT.json with status
PASS_REVIEWED_MODELED_SCORING_ONLY, or FAILED.json with the checked prefix count.
The receipt binds the original report, plan and scoring run and keeps integrated
N4 accepted cells at zero. The reviewer never mutates source evidence, terminates
workers or marks N4 accepted. Production execution requires the passed development
qualification matching this exact code. Production admission and full-bank review
remain unexecuted until a real closed scoring bank exists.

`test_scoring_review.py` uses dictionary fixtures for nine meaningful rejection
tests. `probe_scoring_review.py` runs them and reviews the exact 51 existing saved
development scores from SCORING_BANK_IMPLEMENTATION_V1.json. It reconstructs
their full saved inputs and checks original input and score hashes without
rescoring, new inference or new scenes. The tests exercise partial counts,
reference scopes, wrong edit counts and joins, worker/pipe closure, changed
aggregation/paired counts, activity scope and omitted formatting changes.
These are development checks, not production matrix execution.

Use the isolated metric Python directly from any shell; do not install packages
into the application environment. All helpers pin CPU14 below normal with one
math thread and GPU disabled. The existing Windows scoring lock prevents
concurrent scoring/review helpers. They may coexist with CPU4 component collection
but must not overlap controlled whole-application timing/resource measurements.
No desktop focus/input is used. Each output must be a fresh directory under
local/n4; failed attempts and code bound to receipts must be preserved.

The reviewer reserves 8 MiB for its outputs, rechecks C50/G75-GiB free-space
floors and the 50-GiB shared allowance including 6 GiB pending reservations,
and stops at the original packaging reserve. Its default/max budget is two
hours; the development probe is limited to twelve minutes. Checks occur between
bounded saved artifact reads and report operations; this is not hard preemption
of a single disk/hash/report operation. All detailed references, predictions
and evidence remain private and must not be added to Git.

PowerShell (production path is an example for a future completed scoring run):

```powershell
$jpMetrics='G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpMetrics -B "$jpCode\test_scoring_review.py" -v
& $jpMetrics -B "$jpCode\probe_scoring_review.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\scoring-review-probe-v1'
& $jpMetrics -B "$jpCode\review_scoring_bank.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v1' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-score-review-v1'
```

Command Prompt and Anaconda Prompt (no environment activation required):

```bat
set "JP_METRICS=G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_METRICS%" -B "%JP_CODE%\test_scoring_review.py" -v
"%JP_METRICS%" -B "%JP_CODE%\probe_scoring_review.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\scoring-review-probe-v1"
"%JP_METRICS%" -B "%JP_CODE%\review_scoring_bank.py" --run "G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v1" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-score-review-v1"
```

Choose an unused output suffix for each rerun. An admission/review failure is not
permission to relax coverage, create replacement zero metrics or edit a frozen
source. Preserve it, investigate the specific failure, and qualify a derivative.
