# Application cells within a guarded run

`paced_slot_guarded_v1.py` replaces the old fixed 6-GiB pending estimate with
the existing complete run allocation proof. It preserves the qualified slot's
exact supervisor/coordinator/child identities, CPU14/CPU4 placement, heartbeat,
possible-runtime census, fail-closed access errors, disk floors, packaging
cutoff, per-cell 512-MiB bound and refusal to release a live child.

Inputs are an already held production `Guard`, its saved full resource receipt,
the campaign supervision directory and a fresh direct child under the run's
`cells` folder. The run's complete byte cap includes the cell exactly once.
Current bytes, remaining cell headroom and terminal headroom are checked before
launch and during the cell. The class cannot start a process or update a ledger.
It returns scoped admission/check/release records to the caller. No audio,
profile, model or device is read by this module.

This is unqualified implementation until a compatible application family
checks it and the matching runner owns the full allocation. It cannot be used
to bypass the old runner's gate. Full census must occur initially, periodically
between closed children, and finally. No standalone or simultaneous N4 numerical
worker is authorized by this library.

Eight metadata regressions cover owner/path/proof changes, missing resource
headroom, hidden allocations, incomplete census, current run-cap enforcement
and losing the allocation lock. Run only after exact previous N4 owner closure,
or inside the compatible supervised family probe. No GUI is launched by tests.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "from metric_process import pin; pin(); import unittest,test_paced_slot_guarded_v1 as t; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(t)); raise SystemExit(not r.wasSuccessful())"
```

## CMD and Anaconda Prompt

Use the exact interpreter; no other conda environment is needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "from metric_process import pin; pin(); import unittest,test_paced_slot_guarded_v1 as t; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(t)); raise SystemExit(not r.wasSuccessful())"
```

Tests print their results and create no files. Production inputs must be supplied
by the matching supervised coordinator, using
`ExclusiveApplicationSlot(state, cell, allocation_guard=guard,
allocation_receipt=latest_full_check_binding)`. The preparer/runner family still
needs qualification; this README makes no GUI/resource or N4 acceptance claim.
