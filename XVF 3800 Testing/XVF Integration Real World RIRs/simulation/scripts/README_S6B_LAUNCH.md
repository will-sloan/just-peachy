# S6B atomic I/O launch repair

Purpose: continue the exact frozen epoch2 campaign after two transient Windows atomic status-file replacement failures. The first occurred after23 complete receipts; the second occurred after all64 pilot receipts and the completed pilot index were saved. No native audio result failed or needs to be recomputed.

The separately bound `atomic_io_v1` launch adapter changes only JSON persistence outside the application: every writer gets its own temporary file; PermissionError receives at most20 replacement attempts (under5seconds total scheduled backoff). JSON content/serialization, atomic replacement, input/profile/cache identity and the entire frozen APP remain unchanged. It also avoids a heartbeat/main-thread temporary filename collision. The exact epoch2 validator still hashes source/artifacts and rejects incompatible work.

Inputs: existing epoch2 execution manifest and all original admitted data. Outputs: original epoch2 paths, new invocation receipts, and `ATOMIC_IO_OVERLAY_V1.json`. Model-free writer fixtures are in `validation/atomic_io_v1`. The immutable wrapper itself is hashed separately and retained with the handoff. This is a recoverable orchestration repair, not an accuracy retry.

Preparation (once, already completed for this run) in PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py "$sim\scripts\s6b_launch.py" prepare --epoch epoch2
```

Run/resume the challenge in PowerShell:

```powershell
$env:JP_S6B_SIM = $sim
& $py "$sim\staging\s6b\20260909T230840Z\atomic_io_v1\s6b_launch.py" run --epoch epoch2 --panel challenge --workers 4
```

In Anaconda Prompt or Command Prompt:

```bat
set "JP_S6B_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6B_SIM%\staging\s6b\20260909T230840Z\atomic_io_v1\s6b_launch.py" run --epoch epoch2 --panel challenge --workers 4
```

Use `--panel all --recipes R0 ...` only for the recipe IDs admitted by the shortlist ledger. `--panel pilot --recipes R0 R1 R2 R3 R4 R5 R6 R7` reuses all64 pilot outputs to close an invocation without inference. The original STOP_REQUEST,24-hour deadline, RAM/disk/output reserves and four-worker ceiling remain enforced. Do not edit either frozen snapshot or its manifest. No other system service or antivirus setting is modified.
