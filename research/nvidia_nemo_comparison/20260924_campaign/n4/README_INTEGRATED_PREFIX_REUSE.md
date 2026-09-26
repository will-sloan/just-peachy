# Reuse a verified immutable method prefix

Purpose: preserve the stopped V2 run and avoid recomputing its sealed successful
prefix when only diagnostic history/storage caps change. This does not rescue
its failed or untested cells. `integrated_prefix_reuse.py` first uses the original
qualified evaluator admission, verifies every full publication/projection and
consumer closure, reconstructs the pure prediction without truth, and fingerprints
it. It retains all 1,382 old cell bindings and their original plan and cache keys.

The AST check permits only declared 24-to-64 MiB history limits and the
64-to-128 MiB expanded-artifact limit in event-producing/writing functions.
All prediction/clock/roster/component behavior must match. A derivative plan must
keep the entire population, order, contracts, source and parents; only code,
qualification, reuse receipt and consequent cache keys can change. Each reused
receipt explicitly binds `reused_from` and `execution_source`; its payload and
closure still point to the immutable original producer. No copying, hard links,
deletion, source edits, backdating or silent cache-key substitution occurs.
The production loader requires the exact prefix receipt in the passed derivative
qualification. Full-bank review rechecks each reuse relationship.

Inputs: stopped V2 `--run` and fresh private `--output`. Outputs: ADMISSION,
RESULT with status PASS_REUSABLE_V2_METHOD_PREFIX_ONLY, or FAILED with the checked
count. The original failed/untested denominators remain. No stage acceptance or
new model, metric, GUI, device or audio operation is performed. The report is
private; no full predictions or transcripts are uploaded. The helper uses CPU14
BelowNormal, one math thread, existing writer lock, a 30-minute between-cell
budget, 8-MiB output limit, 6-GiB pending reservations and C:50/G:75 GiB floors.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpPrivate='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$jpN4\integrated_prefix_reuse.py" --run "$jpPrivate\integrated-main-v2" --output "$jpPrivate\integrated-prefix-review-v1"
```

CMD and Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_N4%\integrated_prefix_reuse.py" --run "%JP_PRIVATE%\integrated-main-v2" --output "%JP_PRIVATE%\integrated-prefix-review-v1"
```

Use the existing explicit interpreter; no package installation. Rejection tests
are included in the guarded history probe; its setup supplies source paths and
private temporary storage. A reusable-prefix result is neither a complete-bank
review nor N4 acceptance. The derivative must execute all remaining cells and
then pass its full method/scoring and actual application acceptance checks.
