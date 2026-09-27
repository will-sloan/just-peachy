# Guarded modes bank and independent reviews

## Purpose and scope

This derivative connects the qualified resource guard to the remaining 1,536
modeled modes cases. It calls the unchanged V3 predictor, artifact reader,
prediction conversion, metric worker and numerical score/review functions. It
does not edit the original plan, cached components, failed runs or active sources.
Every new result explicitly binds an EXECUTION_PLAN as well as the original
prediction plan. The new plan records the coordinator source, qualification,
allocation and elapsed limit. Original cache keys continue to describe the
unchanged numerical contract; they are not evidence that the old coordinator ran.

The pure reader in guarded_execution_v1.py requires the new admission, complete
initial/final resource checks and per-cell execution provenance before allowing
the unchanged numerical validators to read the bank. It rejects old/unqualified
coordinators, live owners, probe envelopes, missing resource proof and prefix
reuse. Method and scoring reviews independently verify full artifacts, closure,
conversion, reference support, inputs and aggregate counts. Score review checks
metric algebra and report regeneration; it does not recompute optimal alignments.

The census reader also handles the two retained dispatch receipt spellings,
supervisor_start and supervisor. The latter must bind its dispatch admission;
both bind the exact worker spec, target admission and owner. Ambiguous keys,
changed specs, overlapping outputs and unresolved hosts fail. This repairs the
reader for the preserved main-review dispatch without altering that evidence.
No test directory is generally ignored; the existing 32 individually qualified
fixtures remain, and all physical bytes count.

## Inputs, outputs and resource limits

Inputs are the accepted N2/N3 source already bound by integrated-modes-plan-v3.json,
the 480 saved-audio manifest, 24-job panel, 16 compositions, four additional modes,
sealed component results and immutable V3 qualifications. Evaluator-only truth
is read by scoring and the diagnostic only after predictions are made; it never
enters predict_cell or the production method runner.

Each stage needs a new private output directory. Outputs include EXECUTION_PLAN,
ADMISSION, initial/periodic/final census receipts and RESULT or preserved FAILED.
Methods additionally write full private publication/Controller artifacts and
ordered cell receipts. Scoring writes EVALUATOR, cell scores and REPORT. Private
transcripts, profiles, WAVs, models and evidence stay outside Git.

Production holds the separate reservation-guard.owner.lock for its lifetime and
requires exactly the current supervised driver and no other active N4 allocation.
It never holds the supervisor writer lock while scanning. Every operation checks
CPU14, BelowNormal, one math thread, GPU off, immutable policy, C:50/G:75 GiB floors,
elapsed time and output headroom. Full censuses repeat every 128 cells and at the
end. The sole changed accounting expires only qualified closed ASR/D1 future
reservations, keeps all physical files and live remaining allocations, and retains
2 GiB future reservations plus 0.5 GiB contingency under the 50-GiB ceiling.

Method cap is 1.5 GiB including a 280-MiB per-cell peak and terminal reserve;
scoring cap is 512 MiB; each review cap is 8 MiB. Methods/scoring have at most four
hours, reviews two hours, and metric requests at most 120 seconds. Packaging
starts 2026-09-28 02:48:19 UTC; deadline is 14:48:19 UTC that day. Limits are never
extended automatically. A stop preserves unfinished and failed denominators.
The fresh default output names below must never be reused after an attempt.

## Diagnostic and qualification

probe_guarded_bank_v1.py must run as the sole supervised N4 worker. It uses a
512-MiB/one-hour private allocation and the real production ownership guard. It
runs resource, closure, new-provenance and V3 numerical-review regression tests.
Temporary synthetic admissions are removed by their own TemporaryDirectory
contexts before the complete census; tests leave no unclassified admissions.

It replays 16 predeclared saved-evidence boundaries: all four modes for A0/D0 and
A3/D1, both encoders, using the first matching frozen panel row. Each boundary
runs the old predictor directly and through the new wrapper, compares complete
converted predictions, then compares two requests to the unchanged pinned metric
worker. The evaluator truth is supplied only after both predictions finish. The
probe starts one hidden metric helper, no model inference, GUI, playback, capture,
microphone enumeration, enrollment or Pi connection. It retains seven source
snapshots, full private artifacts, tests, hashes, resource checks and exact helper
closure. A failure is preserved and requires a fresh derivative/output.

GUARDED_BANK_CHECK_V1.json may be sealed only after tests/parity/resource checks
pass, unchanged source verifies and exact probe/metric/supervisor owners exit.
The source gate then permits production method/scoring/review execution. This is
modeled-family qualification only. GUI/resource pacing, naming visibility,
continuity/restart, candidate selection and N4/N5 acceptance are separate. The
inaccessible command-window ownership issue remains a GUI/resource admission
blocker. Live CM5 checks remain deferred until the user reconnects the Pi.

## PowerShell

Use an existing shell. The campaign uses the existing hidden supervisor start
interface with an argv-list worker spec, after verifying the previous exact
worker exit and fresh resource ownership. These are the underlying stage argv;
do not run production alongside an existing worker or outside that supervision.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$metricPython='G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
$stage='research\nvidia_nemo_comparison\20260924_campaign\n4'
$private='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$stage\probe_guarded_bank_v1.py" --plan "$private\integrated-modes-plan-v3.json" --output "$private\guarded-bank-v1-probe-v1"
# After diagnostic qualification and exact closure:
& $jpPython -B "$stage\guarded_method_bank_v1.py" --plan "$private\integrated-modes-plan-v3.json" --output "$private\integrated-modes-guarded-v1" --max-seconds 14400
# After the complete method terminal and exact closure:
& $jpPython -B "$stage\guarded_review_v1.py" --kind method-review --run "$private\integrated-modes-guarded-v1" --output "$private\integrated-modes-method-review-guarded-v1" --max-seconds 7200
# After passed method review and exact closure:
& $metricPython -B "$stage\guarded_scoring_v1.py" --run "$private\integrated-modes-guarded-v1" --review "$private\integrated-modes-method-review-guarded-v1\RESULT.json" --output "$private\integrated-modes-scores-guarded-v1" --cell-timeout 120 --max-seconds 14400
# After complete scoring and exact metric/helper/driver closure:
& $metricPython -B "$stage\guarded_review_v1.py" --kind score-review --run "$private\integrated-modes-scores-guarded-v1" --output "$private\integrated-modes-score-review-guarded-v1" --max-seconds 7200
```

## CMD and Anaconda Prompt

Use the pinned absolute interpreters; no package installation is required.
The same supervision and admission requirements apply to each line.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "METRIC_PY=G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe"
set "JP_STAGE=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_STAGE%\probe_guarded_bank_v1.py" --plan "%JP_PRIVATE%\integrated-modes-plan-v3.json" --output "%JP_PRIVATE%\guarded-bank-v1-probe-v1"
"%JP_PY%" -B "%JP_STAGE%\guarded_method_bank_v1.py" --plan "%JP_PRIVATE%\integrated-modes-plan-v3.json" --output "%JP_PRIVATE%\integrated-modes-guarded-v1" --max-seconds 14400
"%JP_PY%" -B "%JP_STAGE%\guarded_review_v1.py" --kind method-review --run "%JP_PRIVATE%\integrated-modes-guarded-v1" --output "%JP_PRIVATE%\integrated-modes-method-review-guarded-v1" --max-seconds 7200
"%METRIC_PY%" -B "%JP_STAGE%\guarded_scoring_v1.py" --run "%JP_PRIVATE%\integrated-modes-guarded-v1" --review "%JP_PRIVATE%\integrated-modes-method-review-guarded-v1\RESULT.json" --output "%JP_PRIVATE%\integrated-modes-scores-guarded-v1" --cell-timeout 120 --max-seconds 14400
"%METRIC_PY%" -B "%JP_STAGE%\guarded_review_v1.py" --kind score-review --run "%JP_PRIVATE%\integrated-modes-scores-guarded-v1" --output "%JP_PRIVATE%\integrated-modes-score-review-guarded-v1" --max-seconds 7200
```

New metadata tests alone: PowerShell `& $jpPython -B -m unittest discover -s $stage -p test_guarded_bank_v1.py -v`;
CMD/Anaconda `"%JP_PY%" -B -m unittest discover -s "%JP_STAGE%" -p test_guarded_bank_v1.py -v`.
The admitted diagnostic remains necessary; unit tests alone do not authorize a bank.
