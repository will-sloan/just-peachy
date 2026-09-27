# Actual guarded application plan preparation

`paced_panel_plan_guarded_v2.py` reconstructs the selected source-paced plan
from the accepted main/modes score pair, frozen 24-file panel and eight timing
anchors, actual component model assets and qualified application source. It
checks the complete producer manifest and initial/final resource census under
the existing supervisor. It never starts a model, GUI, source, audio device or
Pi connection. It grants no application or N4 acceptance.

Inputs are the original 1,536-case modes plan, exact qualified review results,
strict selection JSON and immutable preparation/qualification receipts. The
proposed six configurations produce 240 paired panel/repeat cells. All assets
and 24 saved WAV files are hashed; no audio is decoded or played. No reference
transcript, score or selection enters the 13-field child payload.

Outputs go to a fresh private folder: `ADMISSION.json`, `EXECUTION_PLAN.json`,
`tests.txt`, source snapshots, `GUARD_INITIAL.json`, `PLAN.json`,
`GUARD_FINAL.json` and `RESULT.json` (or preserved `FAILED.json`). Maximum output
is 16 MiB, elapsed budget 40 minutes, CPU14/BelowNormal, one math thread, GPU off.
The existing complete resource guard preserves the 50-GiB campaign allowance,
C:50/G:75 GiB free floors, sole N4 allocation and packaging cutoff. No shared
ledger mutation occurs. Previous source and attempts remain immutable.

Twelve in-memory regressions cover asset/source/root joins, source changes,
child firewall, changed producer/envelope/receipt joins, budgets, partial tests,
exact owner closure and false execution credit. They run before production
reconstruction, inside the supervised preparation. A passed terminal still
requires independent inspection, exact preparer/supervisor closure and the
published `PACED_PANEL_PLAN_GUARDED_V2_CHECK.json`. Only then does `admit_plan`
recheck that proof, resource receipts and full deterministic reconstruction.
Compatible application/semantic/restart/continuity consumers remain necessary.
The old V4 runner does not admit this schema.

## PowerShell

First inspect the current supervision heartbeat, exact PID creation identities,
all bound sources and complete resource census. Do not dispatch beside another
N4 worker. The campaign continuation prepares the following immutable spec:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
Get-Content 'G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-plan-guarded-v2-worker.json'
Get-Content 'G:\Just_Peachy_N1\20260924_campaign\local\supervision\worker.json'
```

After exact preceding-owner closure and a fresh allocation admission, invoke
the existing `supervisor.start` interface, not the planner as a standalone
worker. The supervisor starts hidden and pins the coordinator as documented in
the supervision README. Once those prerequisites and a dispatch receipt have
been recorded, the PowerShell start command is:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import sys; from pathlib import Path; p=Path('research/nvidia_nemo_comparison/20260924_campaign'); sys.path[:0]=[str(p/'n4'),str(p/'supervision')]; from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path('G:/Just_Peachy_N1/20260924_campaign/local/supervision'),Path('G:/Just_Peachy_N1/20260924_campaign/local/n4/paced-plan-guarded-v2-worker.json')))"
```

The spec's explicit argument list is equivalent to:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4\paced_panel_plan_guarded_v2.py --plan G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-modes-plan-v3.json --main-review G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-score-review-v3-timeout120-v1\RESULT.json --modes-review G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-modes-score-review-guarded-v1\RESULT.json --selection G:\Just_Peachy_N1\20260924_campaign\local\n4\proposed-paced-selection-v1.json --output G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-plan-guarded-v2
```

For a failed attempt, preserve it and choose a fresh spec/output after diagnosis.
Never change a source bound to a running or completed preparation.

## CMD and Anaconda Prompt

The exact application interpreter is required; activating a different conda
environment is unnecessary. Inspection commands in either prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
type G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-plan-guarded-v2-worker.json
type G:\Just_Peachy_N1\20260924_campaign\local\supervision\worker.json
```

To use the same admitted start from CMD/Anaconda, run the supervisor Python
interface after the same recorded admission prerequisites:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import sys; from pathlib import Path; p=Path('research/nvidia_nemo_comparison/20260924_campaign'); sys.path[:0]=[str(p/'n4'),str(p/'supervision')]; from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path('G:/Just_Peachy_N1/20260924_campaign/local/supervision'),Path('G:/Just_Peachy_N1/20260924_campaign/local/n4/paced-plan-guarded-v2-worker.json')))"
```

The campaign continuation records the resulting exact owner identities in the
matching dispatch `STARTED.json`. Direct execution of the planner cannot satisfy
its supervised resource gate. Do not repeat the start for an active run.
After completion, inspect `RESULT.json`, both guard proofs and `tests.txt` in
the private output. Plan preparation is distinct from collecting/reviewing
timed GUI cells and Windows/ARM64 release validation. Live CM5 checks remain
deferred until the user reconnects it.
