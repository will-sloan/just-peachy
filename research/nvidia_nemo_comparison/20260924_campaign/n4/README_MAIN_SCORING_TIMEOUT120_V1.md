# Main scoring with the supported 120-second request limit

## Purpose and scope

This fresh run uses the unchanged qualified `scoring_bank_v3.py` over the
reviewed 7,680-case main method bank. The first run finished with 7,675 scored
rows and five TIMEOUT rows at its default 60-second request limit. Preserve
`integrated-main-scores-v3` and the stopped `main-score-review-advance-v1`
handoff. A separate actual five-case retest at the already-supported
120-second limit must pass, close every exact owner and receive a fresh
resource admission before this run starts. No timeout above 120 is authorized
by this recipe, and failures are preserved rather than overwritten.

Only the request time allowance changes. Metric implementation, pinned
environment, truth, prediction conversion, frozen method artifacts and full
independent review remain the qualified V3 versions. This run performs no new
ASR, diarization or embedding inference and starts no GUI, device, microphone,
playback, training, enrollment or Pi connection.

## Inputs and outputs

Inputs: `local/n4/integrated-main-v3`, its passed
`integrated-main-review-v3.json`, `SCORING_HISTORY_CHECK_V3.json`, the pinned
metric environment and evaluator-only truth/strata already bound by that
qualification. The diagnostic gate is
`local/n4/main-metric-timeout-retest-v1/RESULT.json` with five passed requests
and exact process/pipe closure evidence. The diagnostic alone does not repair
the old bank or establish stage acceptance.

Output: fresh private `local/n4/integrated-main-scores-v3-timeout120-v1`, with
ADMISSION, 7,680 ordered cell score receipts, REPORT and RESULT or preserved
FAILED evidence. Dispatch receipts and the previous closed supervisor state
are in `integrated-main-scoring-timeout120-dispatch-v1`; the worker spec is
`integrated-main-scoring-timeout120-worker-v1.json`. Inspect these and fresh
supervision before starting anything. Never start a duplicate metric worker.

Limits remain CPU14/BelowNormal, one math thread, GPU off, 512 MiB scoring
output, four hours total, the existing six-GiB reservation guard and unchanged
50-GiB campaign allowance, C50/G75-GiB drive floors and packaging cutoff
2026-09-28 02:48:19 UTC. The campaign deadline stays 14:48:19 UTC that day.
The scorer's own admission rechecks all inputs, hashes, owners and storage.

## PowerShell

Use an existing shell. Campaign background dispatch uses the existing
supervisor's hidden process interface and its lifetime/writer locks.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$metricPython='G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
$stage='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $metricPython -B "$stage\scoring_bank_v3.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-v3' --review 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-review-v3.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v3-timeout120-v1' --cell-timeout 120 --max-seconds 14400
```

## CMD and Anaconda Prompt

Use the pinned interpreter without changing the environment:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "METRIC_PY=G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe"
set "N4_STAGE=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%METRIC_PY%" -B "%N4_STAGE%\scoring_bank_v3.py" --run G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-v3 --review G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-review-v3.json --output G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v3-timeout120-v1 --cell-timeout 120 --max-seconds 14400
```

## Independent review after exact completion

Require a sealed `SCORED_MODELED_BANK_REQUIRES_REVIEW` terminal with all
7,680 scored rows, zero failed/untested/unavailable rows, null stop reason,
verified report/score hashes, closed metric owners and pipes, and exited exact
supervisor, venv launcher and actual scoring driver. A zero process exit alone
is insufficient. The old handoff watches the old run only; do not reuse it for
this run. No automatic reviewer is installed by this recipe.

Only after those checks and fresh resource admission, use a new private review
directory. In PowerShell with the variables above:

```powershell
& $metricPython -B "$stage\review_scoring_bank_v3.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v3-timeout120-v1' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-score-review-v3-timeout120-v1'
```

CMD/Anaconda with the variables above:

```bat
"%METRIC_PY%" -B "%N4_STAGE%\review_scoring_bank_v3.py" --run G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v3-timeout120-v1 --output G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-score-review-v3-timeout120-v1
```

The reviewer has its own two-hour/eight-MiB guards. A passed modeled score
review still supplies no actual widget, controlled resource, paced timing,
naming, continuity or restart acceptance. The modes bank and these integrated
checks remain necessary for N4. N5 selected-build validation and final Pi
reconnection packaging also remain open. Live CM5 checks are deferred until
the user reconnects it. Private scores, references, profiles, audio and model
weights stay outside Git; only small count/hash receipts and instructions are
backed up there.
