# Guarded modes score reader for future application planning

Purpose: explicitly join the accepted main V3 scoring review with a complete
guarded V1 modes scoring review. This is a new read-only library; no existing
planner, application runner, policy, source binding or running worker is changed.
It does not grant execution permission, choose backends or accept N4/N5.

Inputs are the exact accepted main score review and the future canonical guarded
modes score-review RESULT.json, their original plans, method reviews, ordered
score receipts, resource execution envelopes and closed metric owners. The reader
verifies full counts (7,680 main, 1,536 modes), exact source and file hashes,
initial/final resource checks, method/score/review joins and aggregate digest.
The original plans must have identical component/audio/runtime contexts apart
from the previously qualified main-only prefix reuse. A modes bank cannot inherit
main-only reuse or acquire acceptance from a progress/partial result.

The modes reader hashes EVALUATOR.json but does not read evaluator truth or
strata contents. It reads score data for provenance only; it does not recompute
metrics. Existing independent score review is still a prerequisite. Each scored
cell must bind its exact original method cell and new scoring EXECUTION_PLAN.
Outputs are only Python return values: review bindings and the original plans.
It writes no files and starts no models, subprocesses, GUI or device connection.

The current V4 panel planner/runner must not be patched to use this library.
A future versioned planner must bind this reader, its tested sources and explicit
policy and require qualification evidence. Matching application, semantic,
restart and continuity consumers need their own compatible qualification. This
library being present or its fixture tests passing is not production qualification.
No production guarded score-review result existed when this library was written;
full positive admission must be tested against the completed real chain later.

`probe_panel_scoring_guarded_v1.py` records the full reader source manifest,
four source snapshots and test log in a fresh private directory. It must run
through the existing supervisor as the sole N4 worker, after a fresh allocation
census and exact prior-owner closure. It uses the qualified production resource
guard, CPU14/BelowNormal, one math thread, GPU off, 8 MiB and 20 minutes. Initial
and final complete resource checks preserve the 50-GiB ceiling and C50/G75-GiB
floors. It does not edit the shared ledger. Tests or an exception preserve their
evidence. Check exact supervisor/probe exit before accepting its result.

Without review arguments the probe checks 11 fixture tests and the real original
main/modes context headers only: PASS_READER_FIXTURES_ONLY. Supplying both review
paths additionally executes the full read-only pair admission and records
PASS_REAL_CLOSED_SCORE_PAIR_READER_ONLY. Neither status prepares or authorizes
a runnable application plan. Do not substitute fixture qualification for the
actual closed score-chain check required before candidate selection.

## Development tests

The tests are in-memory metadata fixtures. Their 1,536 entries are artificial
bindings, not numerical results. They cover failure/partial status, reduced or
boolean denominators, reordered/duplicated cells, foreign paths, changed
execution provenance, mismatched method/review/report joins, wrong role and
rejection of a live producer before any score input is followed.

Run in an available admitted metadata slot, with CPU14/BelowNormal, one math
thread and GPU off. Do not start a standalone N4 helper alongside a worker whose
resource guard requires sole N4 ownership. The command below runs the tests only;
it cannot schedule or authorize production work. Preserve each test log privately.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPython -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n4 -p test_panel_scoring_admission_guarded_v1.py -v
```

CMD and Anaconda Prompt (use the existing interpreter; no environment changes):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n4 -p test_panel_scoring_admission_guarded_v1.py -v
```

The supervised diagnostic uses these underlying arguments (not a second manual
worker). In PowerShell, using the working directory and interpreter above:

```powershell
& $jpPython -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_panel_scoring_guarded_v1.py --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-plan-v3.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/panel-scoring-guarded-probe-v1
```

CMD/Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_panel_scoring_guarded_v1.py --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-plan-v3.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/panel-scoring-guarded-probe-v1
```

For real pair validation append `--main-review MAIN_REVIEW_RESULT_PATH
--modes-review GUARDED_SCORE_REVIEW_RESULT_PATH` and choose a fresh output name.
These inputs become ready only after full modes scoring and independent review.
Any diagnostic must finish or stop before the unchanged packaging reserve.

## Library usage after real inputs and reader qualification exist

From a qualified future planner whose module search path contains this directory:

```python
from panel_scoring_admission_guarded_v1 import read_pair
reviews, main_plan, modes_plan = read_pair(main_review_path, modes_review_path)
```

`main_review_path` is currently the private
`integrated-main-score-review-v3-timeout120-v1/RESULT.json`.
`modes_review_path` will be the separately completed and closed guarded score
review, not the method run or method review. Missing/failed/mismatched evidence
raises an exception and must stop planning. Preserve all failed attempts; do not
rewrite a receipt or rename an old schema to satisfy this reader.

Use the campaign worktree and private evidence root from N4_HANDOFF.md. Do not
publish captions, audio, profiles, weights or raw scores. Hardware remains off;
live CM5 checks are deferred. The existing packaging reserve and deadline apply.
