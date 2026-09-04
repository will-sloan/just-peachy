# H2 post-campaign engineering-evidence watcher

## Purpose

`watch_h2_postcampaign_engineering.ps1` closes two engineering-evidence gaps
after the autonomous H2 v17 scientific controller finishes:

1. it waits for a genuinely quiet Windows host and runs the exact frozen
   Phase-2 R1/R2 serial resource replay until a checksum-bound host-I/O-clear
   comparison exists; and
2. only after that replay is eligible, it measures and validates the common
   application's controlled event-emission-to-Tk-render latency.

The ordering is deliberate. The existing final-package watcher treats the UI
latency receipt as its last readiness signal. Keeping that receipt absent until
the clean resource replay exists prevents final augmentation from starting too
early. The watcher never changes scientific source, policies, thresholds,
development results, held-out results, or the native final package.

The main campaign can briefly publish the generic `BLOCKED` state at a
recoverable orchestration boundary, most importantly while the checksum-bound
pre-freeze selector correction takes over. The watcher deliberately continues
waiting through that generic state. It exits only for `FAILED`, `STOPPED`, or
the explicit terminal statuses `BLOCKED_SCIENTIFIC_RUN` and `BLOCKED_OTHER`.
This keeps the post-campaign replay and UI receipt armed without racing or
duplicating the recovery supervisor.

There is no automatic time limit. If Windows is busy or an ESENT event appears
in the quiet window, the watcher waits and retries. A completed but contaminated
replay is preserved, and the next deterministic `quietNN` attempt is used.

## Inputs

- The completed H2 v17 workspace, results root, and summary root on drive C.
- The immutable v17 protocol/configuration and exact source R1/R2 results.
- `replay_h2_phase2_serial_resources.py` and its source-bound preflight.
- `measure_h2_ui_event_latency.py` and the frozen runtime identity.
- Optional polling, free-space, quiet-window, and inter-job cooldown settings.

The default reserve is 35 GiB, the quiet window is 15 minutes, and the replay
cooldown is 60 seconds. The scientific campaign and its controller are never
stopped or restarted by this watcher.

## Outputs

- An isolated replay workspace/results/summary trio ending in
  `_resource_replay_quietNN`.
- A clean `resource_comparison.json` and host-I/O receipt when eligible.
- `engineering_validation/ui_event_latency_receipt.json`.
- `engineering_validation/postcampaign_engineering_evidence.json`, binding the
  source terminal state, selected replay, UI receipt, and watcher identity.
- `logs/postcampaign-engineering-watcher.jsonl`.

All outputs remain on drive C. No dataset, model weights, credentials, or audio
are copied into this watcher receipt.

## PowerShell

Validate paths and ordering without writing or starting work:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"

powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\scripts\watch_h2_postcampaign_engineering.ps1" `
  -DryRun
```

Run in the current PowerShell window:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\scripts\watch_h2_postcampaign_engineering.ps1" `
  -IntervalSeconds 60 `
  -MinimumFreeGiB 35 `
  -QuietWindowMinutes 15 `
  -CooldownSeconds 60
```

Launch as a hidden persistent helper:

```powershell
$Script = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\scripts\watch_h2_postcampaign_engineering.ps1"
Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList @(
  '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $Script + '"'),
  '-IntervalSeconds', '60',
  '-MinimumFreeGiB', '35',
  '-QuietWindowMinutes', '15',
  '-CooldownSeconds', '60'
)
```

Monitor its durable log without changing the run:

```powershell
Get-Content -LiteralPath `
  ".\automated_runs\h2_complete_product_pipeline_v17\logs\postcampaign-engineering-watcher.jsonl" `
  -Tail 20 -Wait
```

## Anaconda Prompt / Command Prompt

The watcher is a PowerShell orchestration wrapper, so launch it from Anaconda
Prompt or Command Prompt through `powershell.exe`:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\watch_h2_postcampaign_engineering.ps1" -IntervalSeconds 60 -MinimumFreeGiB 35 -QuietWindowMinutes 15 -CooldownSeconds 60
```

The Python tools use the repository `.venv` automatically; no Anaconda
environment needs to be merged with the isolated model environments.

## Recovery and interpretation

- `WAITING_FOR_QUIET_REPLAY_PREFLIGHT` is expected while the controller,
  supervisor, storage guardian, or recent ESENT activity remains visible.
- `QUIET_REPLAY_RETRY_REQUIRED` preserves completed shards and retries the same
  attempt; it does not discard successful work.
- `QUIET_REPLAY_NOT_ELIGIBLE` preserves that attempt and advances to the next
  deterministic attempt.
- `UI_LATENCY_RETRY_REQUIRED` does not affect scientific results and retries
  only the controlled UI benchmark.
- `COMPLETE` means the clean replay and signed UI receipt are both available;
  the already-running final-package watcher can then perform its independent
  validation and augmentation.
