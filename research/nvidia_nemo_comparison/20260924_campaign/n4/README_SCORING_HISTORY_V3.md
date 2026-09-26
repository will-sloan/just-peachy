# V3 evaluator for complete method histories

Purpose: qualify and run an explicit scorer/reviewer for the native-clock/history V3
method bank. `integrated_scoring_adapter_v3.py` reads complete method artifacts
up to 128 MiB, with compressed and expanded SHA-256, exact byte count, gzip CRC,
and strict declared-size checks. It imports the unchanged evaluator conversion
and 32-MiB component-event reader. It never imports the application writer,
model runtime or predictor. Original qualified implementations remain intact.

`scoring_bank_v3.py` preserves exact full-plan coverage, source/evaluator
separation, closed-owner admission, complete-bank review requirements, failed
and untested denominators, metric subprocess timeouts/closure, and original
metric/report calculations. It additionally requires the exact code list and
receipt of INTEGRATED_HISTORY_CHECK_V3, and its own development qualification.
Reused cells must retain the exact original payload and producer receipt,
new plan/cache binding, qualified stopped prefix review and unchanged source/
roster/population join. Unqualified reuse fields on newly executed cells fail
admission. The existing pure prefix validator is imported; it reads producer
source as text for AST comparison without importing the application.
`review_scoring_bank_v3.py` requires that same qualified scorer, stopped owners,
complete score population, reconstructed metric inputs and aggregate reports.

Inputs: the immutable 7,680-cell main or 1,536-cell modes plan, terminal method
run and passed matching method review, full publication/Controller histories,
component events, fixed evaluator truth/strata, and the pinned metric environment.
Production uses SCORING_HISTORY_CHECK_V3.json; absent or changed qualification is
an error. Do not score an active bank or treat a successful prefix as acceptance.

Outputs: fresh private score ADMISSION, per-cell JSON, REPORT and RESULT (or
preserved FAILED); the separate reviewer writes ADMISSION and RESULT/FAILED.
All audio, full captions, profiles, metric inputs, evidence and scores remain
under local/n4. Public qualification contains hashes/counts and no transcripts.
Original scoring schemas are retained. Modeled scoring contributes zero accepted
integrated N4 cells until the remaining campaign acceptance checks pass.

## Development qualification

`probe_scoring_history_v3.py` runs the derivative bank/review suites and artifact
boundary/rejection tests, reconstructs the 51 existing saved metric inputs and
checks their score hashes/algebra, then converts and scores six sealed history-boundary cases plus four sealed
native-clock development cases. Full publications exceed both prior 32/64-MiB
caps. Ten bounded metric requests use the existing owned subprocess and verify
all exact owners exit. The saved 51 alignments are not recomputed.

The probe observes the existing main bank, exact process creation identities,
supervision heartbeat, command, all plan bindings, and resource census before
and after. It never consumes an active prefix for scoring. This is non-controlled
development on CPU14 BelowNormal, one math thread, GPU disabled; it supplies no
latency/resource/GUI acceptance. Census uncertainty is recorded and cannot
authorize later exclusive application runs. No microphone, playback, GUI or Pi
is used. Probe budget: 20 minutes checked between operations, 120 seconds per
metric request, 8 MiB private output, drive floors C:50/G:75 GiB and campaign
50-GiB allowance including the active method bank remaining allocation,
6 GiB pending reservations and 0.5 GiB contingency. The 8-MiB probe output is
charged to that contingency. It checks all 1,382 reused producer receipts as
metadata only; it never scores an active prefix. Synthetic temporary files are
created only below the fresh private probe output and removed by their own
TemporaryDirectory contexts. Failed attempts and source snapshots are retained.

## PowerShell

Run from the campaign checkout. Each output directory must be new. These
commands use the existing metric environment; no install or download is needed.

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$metricPython = 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
$stage = 'research\nvidia_nemo_comparison\20260924_campaign\n4'
$privateN4 = 'G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $metricPython -B "$stage\probe_scoring_history_v3.py" --output "$privateN4\scoring-history-v3-probe-v1"
```

After the method bank stops and `integrated_bank_v3.py review` passes, run the
following stages sequentially, checking each RESULT before proceeding:

```powershell
& $metricPython -B "$stage\scoring_bank_v3.py" --run "$privateN4\integrated-main-v3" --review "$privateN4\integrated-main-review-v3.json" --output "$privateN4\integrated-main-scores-v3"
& $metricPython -B "$stage\review_scoring_bank_v3.py" --run "$privateN4\integrated-main-scores-v3" --output "$privateN4\integrated-main-score-review-v3"
```

For the separately completed modes bank, substitute `integrated-modes-v3`,
`integrated-modes-review-v3.json`, `integrated-modes-scores-v3` and
`integrated-modes-score-review-v3`. A main-bank receipt cannot stand in for modes.
Scorer defaults: 60 seconds/cell, four hours/run, 512 MiB output. CLI permits up
to 120 seconds/cell. Review permits two hours and 8 MiB output. Both retain
shared allowance/drive/packaging checks and the existing metric writer lock.

## CMD and Anaconda Prompt

Use the absolute existing interpreter even if an unrelated conda environment is
active. Do not change its packages. The same commands work in both shells:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "METRIC_PY=G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe"
set "N4_STAGE=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "N4_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%METRIC_PY%" -B "%N4_STAGE%\probe_scoring_history_v3.py" --output "%N4_PRIVATE%\scoring-history-v3-probe-v1"
```

Only after closed method-bank review and development qualification:

```bat
"%METRIC_PY%" -B "%N4_STAGE%\scoring_bank_v3.py" --run "%N4_PRIVATE%\integrated-main-v3" --review "%N4_PRIVATE%\integrated-main-review-v3.json" --output "%N4_PRIVATE%\integrated-main-scores-v3"
"%METRIC_PY%" -B "%N4_STAGE%\review_scoring_bank_v3.py" --run "%N4_PRIVATE%\integrated-main-scores-v3" --output "%N4_PRIVATE%\integrated-main-score-review-v3"
```

The probe is the supported bounded test command. Its tests include exact
128-MiB roundtrip, over-limit decompression, invalid declared sizes, compressed
hash/expanded hash/CRC failures, unqualified code substitutions, active-owner
rejection, original full-bank denominator tests, real owned metric lifecycle
tests, score-review corruption tests, and source/roster/producer/closure/digest
rejection tests in test_integrated_prefix_reuse.py and test_scoring_reuse_v3.py. It preserves evidence for qualification;
standalone unittest output does not authorize production execution.

The result proves derivative compatibility and development behavior only.
Production terminal admission/scoring/review remain to be executed; actual
source-paced GUI/resource, continuity/restart and N5 deployment acceptance are
separate. Live CM5 validation remains deferred until the user reconnects it.
