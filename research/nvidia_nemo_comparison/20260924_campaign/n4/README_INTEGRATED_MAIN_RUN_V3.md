# Full-bank continuation after the diagnostic-history boundary

Actual dispatch: 2026-09-26 17:38:49 UTC; supervisor 31132/create
1790444329.8372655 and worker 46448/create 1790444329.9990232. Start receipt
INTEGRATED_MAIN_STARTED_V3.json binds the exact plan/worker and verification
past the original failed cell at 1,390/7,680. The current run is already active;
use the read-only status commands below and do not start a duplicate.

Purpose: continue the exact 7,680-cell main bank using a new qualified plan and
run, preserving integrated-main-v2 and all failed probes. V2 stopped with 1,382
completed, one failed and 6,297 untested cells. The failed cell was
A1_D1_E0_N2_S45_03_04_O0_open_with_names. Diagnostic publication history exceeded
24 MiB; the complete publication needed 73,245,202 bytes after that cap was
raised. The V3 derivative keeps all events with 64-MiB individual history caps
and a 128-MiB expanded-artifact cap. It changes no model, clock, roster or
prediction policy. Its 280-MiB cell reservation is included in the run budget.

Prerequisites: passed INTEGRATED_HISTORY_CHECK_V3.json matching all code; stopped
original owners; passed exact integrated-prefix-review-v1/RESULT.json; unchanged
ASR/D0/D1 component reviews and source preparation. The new qualification binds
the exact prefix review. Reused cells retain original payload/closure bindings
and explicit original-producer provenance. Failed/untested cells are executed
by the new derivative. No historical evidence is overwritten or deleted.

Preparation inputs are the three passed component reviews and prefix receipt.
Output is a fresh integrated-main-plan-v3.json binding all 7,680 new cache keys.
Run outputs are fresh ADMISSION, per-cell receipts/histories, PROGRESS and
terminal RESULT. The final review requires complete output and stopped exact
owners, and verifies all reused provenance and full histories. It does not
establish actual GUI/latency/resource performance or N4 acceptance.

The supervised production allocation is recorded in the stage start receipt.
For the commands below, admission must verify that 5 GiB for new run output,
6 GiB pending reservations and 0.5 GiB contingency fit within 50 GiB total
private campaign storage. All existing attempts count. Retain C:50/G:75 GiB.
One model-free CPU14 BelowNormal worker runs at a time, hidden; no GUI,
microphone, playback, model inference or Pi contact. The existing supervisor
phase/start interfaces own dispatch; do not edit their shared ledgers manually.

## PowerShell

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpPrivate='G:\Just_Peachy_N1\20260924_campaign\local\n4'
# Read current state; never start a duplicate.
Get-Content -LiteralPath "$jpPrivate\integrated-main-v3\PROGRESS.json"
Get-Content -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\local\supervision\worker.json'
# Prepare only once, after all prerequisites pass; use the exact D0 review path
# from the prior immutable plan's context.reviews.D0 (not a guessed filename).
$d0Review=(Get-Content -LiteralPath "$jpPrivate\integrated-main-plan-v2.json" -Raw | ConvertFrom-Json).context.reviews.D0.path
& $jpPython -B "$jpN4\integrated_bank_plan_v3.py" --asr-review "$jpPrivate\asr-full-bank-review-v1\REVIEW.json" --d0-review $d0Review --d1-review "$jpPrivate\d1-full-bank-review-v3\REVIEW.json" --reuse-review "$jpPrivate\integrated-prefix-review-v1\RESULT.json" --scope main --output "$jpPrivate\integrated-main-plan-v3.json"
# Foreground reproduction only when no supervised bank is active and resources
# have been freshly admitted. The campaign itself uses the supervisor.
& $jpPython -B "$jpN4\integrated_bank_v3.py" run --plan "$jpPrivate\integrated-main-plan-v3.json" --output "$jpPrivate\integrated-main-v3" --allocation-gib 5
# Only after a complete terminal result and exact worker exit:
& $jpPython -B "$jpN4\integrated_bank_v3.py" review --run "$jpPrivate\integrated-main-v3" --output "$jpPrivate\integrated-main-review-v3.json"
```

## CMD / Anaconda Prompt

Use the same existing interpreter without installing or changing packages.
Preparation can use the PowerShell command above from either shell with
`powershell -NoProfile`, or run the planner directly with the three verified
review paths and prefix receipt. For an already prepared plan:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
type "%JP_PRIVATE%\integrated-main-v3\PROGRESS.json"
type "G:\Just_Peachy_N1\20260924_campaign\local\supervision\worker.json"
rem Prepare only once after prerequisites, using a fresh plan output:
"%JP_PY%" -B "%JP_N4%\integrated_bank_plan_v3.py" --asr-review "%JP_PRIVATE%\asr-full-bank-review-v1\REVIEW.json" --d0-review "G:\Just_Peachy_N1\20260924_campaign\local\n4\d0-bank-review-v1\REVIEW.json" --d1-review "%JP_PRIVATE%\d1-full-bank-review-v3\REVIEW.json" --reuse-review "%JP_PRIVATE%\integrated-prefix-review-v1\RESULT.json" --scope main --output "%JP_PRIVATE%\integrated-main-plan-v3.json"
rem Only with no active bank and fresh resource admission:
"%JP_PY%" -B "%JP_N4%\integrated_bank_v3.py" run --plan "%JP_PRIVATE%\integrated-main-plan-v3.json" --output "%JP_PRIVATE%\integrated-main-v3" --allocation-gib 5
rem Only after complete terminal and exact owner exit:
"%JP_PY%" -B "%JP_N4%\integrated_bank_v3.py" review --run "%JP_PRIVATE%\integrated-main-v3" --output "%JP_PRIVATE%\integrated-main-review-v3.json"
```

All output paths must be new for a reproduction; existing production paths are
immutable. Read the stage start receipt before running anything. The V2 scorer
is intentionally incompatible with this changed plan/artifact cap: qualify an
explicit evaluator derivative before full-bank scoring. The modes panel,
selected source-paced GUI/resource, continuity/restart, final N4 report and N5
Windows/ARM64 packaging remain separate. Live CM5 validation waits for the user
to reconnect the Pi. The fixed packaging reserve and campaign deadline remain.
