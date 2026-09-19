# S4.5 exact restoration recovery

`s45_restore_recovery.py` runs one bounded recovery after a hardware batch records failed restoration and the supervisor has fully closed. It reuses the existing, unchanged S4 `restore_exposed`/`recover` implementation, which acquires the shared hardware lease, disables packed input and verifies the exact original exposed settings, identity, USB width and ancillary readbacks. It plays no audio and runs no models. This is recovery of the captured starting state, not a new capture recipe.

Inputs are the specified S4.5 hardware batch's `initial_state.json` and failed `restoration.json`, cleared owner markers, closed supervisor receipt and existing recorder runtime. Original failure evidence is preserved. Outputs beside that failure are `restoration_recovery.json`, `recovery_commands` and `recovery_driver_receipt.json`, with original/code hashes and actual outcome. The wrapper refuses an existing recovery or prior driver receipt; inspect any failed recovery before deciding a separately recorded next action. All ordinary S4.5 time, storage and ownership bounds still apply.

PowerShell, only after the supervisor and hardware/model children close:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s45_restore_recovery.py --batch canonical_20260909T071736_0228fe
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s45_restore_recovery.py --batch canonical_20260909T071736_0228fe
```

Use the recorder Python above; no dependency install is needed. The underlying exact float32/getter behavior is covered by `test_s4_restore.py` and documented in `README_S4_RESTORE.md`. Compile the wrapper without hardware using `python -m py_compile s45_restore_recovery.py`. Compilation alone is not restoration evidence. A successful recovery must also pass the unchanged prior-restoration gate before a new supervisor resumes identical frozen inputs within the original deadline.
