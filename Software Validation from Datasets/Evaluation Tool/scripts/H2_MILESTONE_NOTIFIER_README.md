# H2 milestone notifier

## Purpose

`watch_h2_milestones.ps1` watches the durable milestone stream produced by the
restart-safe H2 product-pipeline controller. It plays an audible Windows system
sound when a new phase completes, when held-out evaluation opens, and when the
complete H2 program finishes. A failure/block status uses the Windows error
sound.

The notifier is operational only. It never starts, stops, retries, calibrates,
or modifies scientific evaluation work. When attached to an existing campaign,
the milestones already present are recorded as its baseline without producing
old alerts. A locked file prevents two notifier instances from running against
the same workspace.

On Windows, all controller JSON and milestone reads explicitly allow read,
write, and delete sharing. The notifier therefore cannot block the controller's
atomic publication of a new state snapshot while it is polling.

## Inputs and outputs

Inputs:

- `<workspace>\program_state.json`;
- `<workspace>\milestones.jsonl`.

Outputs under `<workspace>\milestone_notifier`:

- `notifier_state.json`: durable set of milestone IDs already announced;
- `notifier_events.jsonl`: start, milestone, status, completion, and failure
  events;
- `notifier.lock`: single-process operating-system lock.

All paths remain on C:. No datasets, model files, result trees, or caches are
copied.

## PowerShell or Anaconda Prompt

Anaconda activation is not required because the notifier is PowerShell-only.
Open PowerShell or Anaconda Prompt and run:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\watch_h2_milestones.ps1 -DryRun
.\scripts\watch_h2_milestones.ps1 -IntervalSeconds 30
```

`-DryRun` reads only the existing controller state and milestone stream. It
does not create the notifier directory, lock, state, or event log.

To launch it as a hidden background helper:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Notifier = (Resolve-Path '.\scripts\watch_h2_milestones.ps1').Path
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
  '-NoProfile',
  '-ExecutionPolicy', 'Bypass',
  '-File', "`"$Notifier`"",
  '-IntervalSeconds', '30'
)
```

## Windows Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\watch_h2_milestones.ps1 -DryRun
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\watch_h2_milestones.ps1 -IntervalSeconds 30
```

## Monitoring and recovery

The watcher exits after final completion or a terminal failure/block status. If
Windows restarts during the campaign, run the launch command again. Its durable
state prevents already announced milestones from being replayed.

The scientific monitor remains the detailed progress display:

```powershell
.\scripts\monitor_h2_product_program.ps1 -Follow -IntervalSeconds 30
```
