# Main V3 review and modes-plan execution checkpoint

## Purpose

Record the first complete 7,680-case main method collection, its supervised
full-artifact review, and the separate 1,536-case modes plan. These are modeled
application-method results from accepted saved component evidence. Collection,
plan construction and review preparation confer no integrated N4 acceptance.
No GUI, model inference, microphone, playback, enrollment or Pi connection is
started by the review or plan-construction commands below.

## Inputs and outputs

The main run is `local/n4/integrated-main-v3`, bound to
`local/n4/integrated-main-plan-v3.json`. It finished 7,680/7,680 with zero failed
and untested rows. Exact numerical worker 46448/1790444329.9990232 and supervisor
31132/1790444329.8372655 exited; supervision reported exit zero at
2026-09-26 23:43:46 UTC. The stale RUNNING label in PROGRESS.json is historical;
the terminal RESULT and exact process identities control stage transitions.

The review reads every complete publication, projection, full display history,
closure, source/cache join and qualified reused-prefix producer. Its output is
`local/n4/integrated-main-review-v3.json`; require
PASS_REVIEWED_MODELED_METHOD_BANK_ONLY and all_full_artifacts_and_closures_verified
before scoring. The dispatch admission and preserved prior supervision files
are in `local/n4/integrated-main-review-dispatch-v3`. Its worker specification
is `local/n4/integrated-main-review-worker-v3.json`. The existing supervisor
started child 36868/1790468573.2251587 under host 41592/1790468573.094462 on
2026-09-27 at 00:22:53 UTC. Both use CPU14/BelowNormal; math threads are one and
GPU use is disabled. This is non-controlled metadata review, not resource or
latency qualification. Never start a duplicate while either exact owner lives.

Modes inputs are the accepted ASR, D0 and D1 component reviews plus the same
frozen source, galleries, audio-only 480-job manifest and fixed 24-job panel.
The generated `local/n4/integrated-modes-plan-v3.json` has exactly 1,536 rows,
24 jobs and four non-main modes across the 16 compositions. It retains the
main context except its inapplicable prefix-reuse field. No reference truth
enters the plan, and modes prefix reuse is absent. Private construction receipts
are in `local/n4/integrated-modes-plan-preparation-v3`; plan SHA-256 is
`ab3a6f79b13cbd200b24d72c7749814cf1f170f611b828eb603b86c9b2cfbfaf`.

Both commands below refuse an existing destination. They document the executed
inputs; do not rerun over preserved evidence. A future justified rerun requires
a fresh path and a new ownership/resource admission.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpPrivate='G:\Just_Peachy_N1\20260924_campaign\local\n4'
$env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'
$env:CUDA_VISIBLE_DEVICES='-1'; $env:PYTHONDONTWRITEBYTECODE='1'
& $jpPython -B "$jpN4\integrated_bank_v3.py" review --run "$jpPrivate\integrated-main-v3" --output "$jpPrivate\integrated-main-review-v3.json"
& $jpPython -B "$jpN4\integrated_bank_plan_v3.py" --asr-review "$jpPrivate\asr-full-bank-review-v1\REVIEW.json" --d0-review "$jpPrivate\d0-bank-review-v1\REVIEW.json" --d1-review "$jpPrivate\d1-full-bank-review-v3\REVIEW.json" --scope modes-panel --output "$jpPrivate\integrated-modes-plan-v3.json"
```

The actual long review was dispatched through the existing supervisor, using
its immutable worker spec and `supervisor.py start --root` interface. See
`../supervision/README.md` for status and dispatch commands. Do not edit shared
campaign/worker records manually or reuse a worker slot before exact owners exit.

## CMD and Anaconda Prompt

Use the same existing interpreter without installing or changing packages:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set CUDA_VISIBLE_DEVICES=-1
set PYTHONDONTWRITEBYTECODE=1
"%JP_PY%" -B "%JP_N4%\integrated_bank_v3.py" review --run "%JP_PRIVATE%\integrated-main-v3" --output "%JP_PRIVATE%\integrated-main-review-v3.json"
"%JP_PY%" -B "%JP_N4%\integrated_bank_plan_v3.py" --asr-review "%JP_PRIVATE%\asr-full-bank-review-v1\REVIEW.json" --d0-review "%JP_PRIVATE%\d0-bank-review-v1\REVIEW.json" --d1-review "%JP_PRIVATE%\d1-full-bank-review-v3\REVIEW.json" --scope modes-panel --output "%JP_PRIVATE%\integrated-modes-plan-v3.json"
```

## Next gates and storage

Once the main review passes and its exact owner exits, use the qualified V3
scorer and independent score reviewer described in README_SCORING_HISTORY_V3.md.
Preserve this review and its supervisor history before reusing the worker slot.
An exit-zero supervisor result alone does not establish complete score coverage.

The modes plan has not been run. The matching 384 main-panel cells occupy
214,157,706 bytes; four times that is 856,630,824 bytes. Adding the qualified
280-MiB per-cell peak gives a rough 1.071-GiB planning estimate; other modes
can differ, so this is not a guaranteed bound. A 1.25-GiB allocation does not
fit the current conservative 50-GiB accounting: existing files plus 6-GiB
pending and 0.5-GiB contingency already project to about 49.233 GiB after
planning. Reconcile stage reservations through a verified permitted admission
before executing modes. Do not reduce denominators, start a predictably
undersized run, overwrite evidence, weaken guards or manually edit the shared
ledger. C:50/G:75-GiB drive floors remain separate and currently pass.

The inaccessible cmd.exe PID 40092 still prevents controlled GUI/resource
admission; the earlier user clarification is pending. It does not turn this
metadata review into a controlled measurement. Actual selected applications,
naming/timing, continuity/restarts, N4 acceptance, then N5 Windows/ARM64 software
validation and accepted-configuration release remain. The Pi stays offline;
on-device checks await reconnection. Packaging reserve starts 2026-09-28
02:48:19 UTC and the final deadline is 14:48:19 UTC that day.
