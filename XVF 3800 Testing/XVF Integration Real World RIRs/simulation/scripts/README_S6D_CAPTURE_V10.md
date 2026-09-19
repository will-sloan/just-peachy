# Capture owner V10

`s6d_capture_owner_v10.py` adds one explicitly authorized recovery-admission branch to V9. It accepts only the new `closed_recorded_telemetry_fresh_restore` kind through the V5 file-only verifier, passing exact prior owner/restoration/initial-state bindings. A failed verifier cannot fall through to an older recovery branch. V9 capture, scientific controls, telemetryV2 lifecycle, pure restoration policy, TCP preflight, payload40GiB, storage floors, pass/time caps and prior recovery branches remain unchanged.

Inputs remain the exact capture plan, authorization, batch and attempt IDs. The authorization binds 25 canonical owner dependencies including both V4 and V5 recovery helpers/READMEs; the separate unchanged supervisor bridge makes the combined execution graph26. Historical producer copies are nested under each recovery's source review, avoiding duplicate basenames in the owner graph. Outputs remain existing capture/ledger/restoration receipts in new admitted destinations. A source freeze does not admit execution or clear the unresolved hardware marker.

PowerShell, file-only plan check:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_capture_owner_v10.py" check-plan --plan 'CAPTURE_PLAN.json' --authorization 'CAPTURE_AUTHORIZATION.json'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_capture_owner_v10.py" check-plan --plan "CAPTURE_PLAN.json" --authorization "CAPTURE_AUTHORIZATION.json"
```

Only the root's separately reviewed literal queue may use `execute --plan ... --authorization ... --batch ... --attempt-ids ...`. No new execution command or approval is supplied here. Focused fake-service and owner-admission reproduction is documented in [README_S6D_CLOSED_TELEMETRY_RESTORE_V5.md](README_S6D_CLOSED_TELEMETRY_RESTORE_V5.md); the unchanged capture behavior and full inputs/outputs remain documented in README_S6D_CAPTURE_V5.md and README_S6D_CAPTURE.md.
