# Current integrated main run

Purpose: operate and review the already-started 7,680-case model-free method
bank. Do not start a duplicate. INTEGRATED_MAIN_STARTED_V2.json binds the private
plan, admitted source, passed component reviews and exact worker identities.
Use the bank's own PROGRESS.json; shared panel_progress.json describes old D1
work. The supervisor heartbeat remains in local/supervision/worker.json.

Inputs: integrated-main-plan-v2.json; reviewed ASR 1,920, D0 960 and D1 960
components; the original 480 saved mono jobs, 16 compositions and fixed primary
open roster. Outputs: local/n4/integrated-main-v2 with full publication and
Controller artifacts and terminal status. No new neural inference or GUI runs.
The actual run allocation is **5 GiB**, retaining 6 GiB pending reservations
and 1 GiB contingency within the original 50-GiB shared allowance. The 140-MiB
cell reservation and C50/G75-GiB floors remain enforced. CPU14, Below Normal,
one math thread, GPU disabled. There is no automatic failed-run resume.

PowerShell inspection and later review:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
Get-Content -LiteralPath "$jpLocal\n4\integrated-main-v2\PROGRESS.json"
Get-Content -LiteralPath "$jpLocal\supervision\worker.json"
# After complete terminal output and verified exact worker exit:
& $jpPython -B "$jpCode\integrated_bank_v2.py" review --run "$jpLocal\n4\integrated-main-v2" --output "$jpLocal\n4\integrated-main-review-v2.json"
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
type "%JP_LOCAL%\n4\integrated-main-v2\PROGRESS.json"
type "%JP_LOCAL%\supervision\worker.json"
rem After complete terminal output and verified exact worker exit:
"%JP_PY%" -B "%JP_CODE%\integrated_bank_v2.py" review --run "%JP_LOCAL%\n4\integrated-main-v2" --output "%JP_LOCAL%\n4\integrated-main-review-v2.json"
```

Preparation and foreground run commands are in README_INTEGRATED_BANK_CLOCK_V2.md.
The automatic launch used the existing supervisor's phase/start interface and
private integrated-main-worker-v2.json with `--allocation-gib 5`; both processes
were hidden. Prior worker/campaign/spec snapshots are preserved under
local/n4/integrated-main-dispatch-v2. No shared ledger was changed manually.

The explicit evaluator derivative is qualified in SCORING_CLOCK_CHECK_V2.json.
See README_SCORING_CLOCK_V2.md for its pure 64-MiB reader and PowerShell/CMD/
Anaconda scoring/review commands. The original 32-MiB scoring code and checks
remain intact. Only a passed complete-bank review admits scoring. Prepare
and execute the separate 1,536-case modes bank, then use scored accepted evidence
for baseline plus at most five candidates, actual paced GUI/resource checks,
continuity and restart. These method outputs do not establish integrated stage
acceptance, real-time latency, complete-stack resource fit or CM5 operation.
