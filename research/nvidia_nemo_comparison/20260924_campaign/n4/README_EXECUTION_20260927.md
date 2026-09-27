# Main V3 review and modes-plan execution checkpoint

## 2026-09-27 03:44 UTC - Five timeout retests passed; fresh full scoring active

The original main scoring attempt sealed 7,675 SCORED rows and five TIMEOUT
rows out of 7,680 complete predictions. Its exact supervisor, launcher,
scoring driver and all metric owners exited. The old automatic handoff stopped
without dispatching review because this was PARTIAL_MODELED_BANK_SCORING.
MAIN_SCORING_PARTIAL_V3.json and README_MAIN_SCORING_PARTIAL_V3.md preserve
that outcome and a provisional 16-composition table, checked against the
original sealed totals. It is not a reviewed shortlist or acceptance report.

All five missing cases subsequently passed with the qualified implementation's
already-supported 120-second request limit. They took 64.860, 67.703, 76.265,
67.610 and 65.421 seconds. METRIC_TIMEOUT_RETEST_CHECK_V1.json binds the actual
saved-input retest and all five exact worker/pipe closures. Metric code,
environment and predictions were unchanged. The original failures remain intact;
the diagnostic alone does not repair or independently review the full bank.

A fresh unchanged V3 scorer now runs in the private directory
integrated-main-scores-v3-timeout120-v1. MAIN_SCORING_TIMEOUT120_START_V1.json
binds its verified admission: supervisor 7636/1790480408.590266, venv launcher
24252/1790480408.7480931, actual driver 49484/1790480408.7788572, run ID
c994c33432a94dc8a3d4fd6a1885395a. All use CPU14/BelowNormal. The limit is
120 seconds per metric request, four hours total and 512 MiB output. No model
inference is repeated. Fresh unchanged shared-budget admission passed at
49.279520 GiB against 50 GiB; this is metadata evaluation, not a controlled
resource measurement. Preserve the healthy worker and its bound source.

README_MAIN_SCORING_TIMEOUT120_V1.md contains inputs, outputs and complete
PowerShell/CMD/Anaconda scoring and independent-review recipes. The old waiter
watches only the old run and must not be reused. No new automatic reviewer is
active. After this exact scorer and all children exit, require all 7,680 scores
with zero unavailable rows and a null stop reason, then independently review
into integrated-main-score-review-v3-timeout120-v1 using the qualified V3
reviewer and fresh resource admission. Do not accept exit zero by itself.

N2/N3 are accepted within their recorded offline component scope. Modes
execution/scoring/review, production reservation-guard integration, actual
selected GUI/resource/timing/naming/continuity/restart checks, N4 acceptance
and final N5 Windows/ARM64 validation remain open. The inaccessible cmd.exe
PID40092 (creation 2026-09-25 13:00:00.031140 UTC) still prevents controlled
GUI/resource admission; the existing ownership clarification is unanswered.
Easy Pi reconnection, storage-aware shared GUI/backend choices and rollback
remain required by n5/PI_RECONNECTION_REQUIREMENTS.md. The Pi stays offline;
no software is claimed newly installed or validated on it. Packaging reserve
and deadline remain 2026-09-28 02:48:19 and 14:48:19 UTC.

## 2026-09-27 02:37 UTC - Reservation calculation qualified; production integration still open

The fresh reservation_budget_v1 library and its admitted read-only probe passed
26 boundary/failure tests. RESERVATION_BUDGET_CHECK_V1.json binds 94 source
files and private reservation-budget-v1-probe-v1 evidence; exact probe owner
44304/1790476363.121994 exited. The probe reverified all 2,880 ASR/D1 result
bindings and their closed exact owners. It included current scorer, waiter and
probe output remainders, all physical bytes, a proposed 1.5-GiB modes request,
2 GiB retained future allowance and 0.5 GiB contingency: 47.256897 GiB against
the unchanged 50-GiB ceiling. No evidence was removed or credited as free.

This qualifies the calculation only. Its active allocation set is explicit and
caller supplied; complete allocation-census qualification and integration into
fresh method/scorer/reviewer/application guards remain required. No production
guard was replaced and no modes worker was admitted. Do not treat this receipt
as permission to bypass a frozen guard. README_RESERVATION_BUDGET_V1.md includes
purpose, inputs/outputs and PowerShell/CMD/Anaconda recipes and next gates.

At this observation, main scoring had 3968 receipts: 3964 SCORED and
4 TIMEOUT. Private main-scoring-timeout-observation-v2/RESULT.json binds every
unavailable row and its unchanged method input. The current scorer and guarded
handoff retain their exact identities and CPU14/BelowNormal limits. Finish the
active run before any targeted metric repair; the handoff requires zero missing
metrics and will refuse a partial terminal. Do not overwrite failed receipts.

N2/N3 accepted offline component evidence remains the upstream authority. Modes
execution/scoring/review, selected actual GUI/resource/timing/naming/continuity/
restart checks, N4 acceptance and N5 final validation remain incomplete. The
inaccessible cmd.exe PID40092 ownership question remains pending; controlled
GUI/resource admission is still blocked. The Pi remains offline. Packaging
reserve is 2026-09-28 02:48:19 UTC; deadline 14:48:19 UTC that day, unchanged.

## 2026-09-27 01:54 UTC - Two metric timeouts; active run preserved

A fresh per-cell inspection found two TIMEOUT / NOT_SCORED_TIMEOUT receipts
at indices 00888 and 00889 (about 60.5 and 60.8 seconds). The numerical method
outputs are complete, but these metrics are unavailable. The scorer continues
to produce later receipts and its supervisor has no stop reason. Preserve the
active worker and both failures; do not modify its source or start a duplicate.

Private main-scoring-timeout-observation-v1/RESULT.json binds both receipts,
method inputs, current owners and counts. Once this run terminates and exact
owners exit, targeted metric repair needs a fresh bounded, qualified derivative
followed by independent full-score review. The live automatic handoff requires
zero unavailable scores, so it must refuse this partial result unless later
verified evidence satisfies that gate; no failed receipt may be overwritten.
Receipt counts below denote progress, not all-scored coverage or acceptance.

## 2026-09-27 01:47 UTC - Guarded automatic score-to-review handoff active

The bounded waiter `advance_main_score_review_v1.py` is live as exact owner
12420/1790473329.108624 on CPU14/BelowNormal. Its 13 development tests passed;
SCORE_REVIEW_ADVANCE_CHECK_V1.json binds all eight dependencies and the closed
test owner. This qualifies the ownership/failure checks, not an actual review
handoff or N4 acceptance. At 01:46 the main scorer had accounted for 896 of
7,680 receipts with no stop reason; independent review remains outstanding.

Private waiter evidence is `local/n4/main-score-review-advance-v1` and immutable
launch records are `local/n4/main-score-review-advance-v1-launch/STARTED.json`
and VERIFIED_WAITING.json. Inspect these, any READY/RESULT/FAILED receipt and
fresh supervision before manually dispatching a review. Do not start a second
waiter or manual reviewer while its exact owner lives. Its source, README,
tests and qualification are now bound and must remain unchanged.

The waiter polls once per minute for this exact scoring run only. It requires
a successful complete terminal, all 7,680 scores, closed metric requests and
the exact supervisor, venv launcher and actual scoring driver to have exited.
It rechecks source hashes, storage and ownership, preserves prior supervision,
and invokes the existing supervisor once for independent review into
`local/n4/integrated-main-score-review-v3`. A failure preserves FAILED evidence;
an ambiguous dispatch is never retried automatically. The waiter has a five-
hour maximum and obeys the unchanged packaging cutoff. It does not start the
modes bank, GUI work or N5, and it does not change the hourly Codex follow-up.
See README_SCORE_REVIEW_ADVANCE_V1.md for purpose, inputs, outputs, exact
admission conditions and PowerShell/CMD/Anaconda instructions.

## Update at 2026-09-27 01:34 UTC

The full main review passed; MAIN_METHOD_REVIEW_V3.json records its exact
closed owners and 7,680-case coverage. Main scoring is now running through
integrated-main-scoring-worker-v3.json, with private dispatch/evidence under
integrated-main-scoring-dispatch-v3 and integrated-main-scores-v3. Observe the
actual driver 51780/1790472224.6372485 beneath the venv launcher, and require
complete scores plus independent review before acceptance. Follow the scorer
and review commands in README_SCORING_HISTORY_V3.md only after their exact
predecessor exits; do not launch a duplicate. The earlier review/plan commands
below describe completed work and refuse existing output paths.

RESERVATION_RECONCILIATION_20260927.md records the audited closed component
allocations and candidate budget correction. No qualified replacement guard
exists yet, so the modes run is still not admitted. All other acceptance and
Pi reconnection limits below remain in force.


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
