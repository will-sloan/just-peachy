# Capture owner V11

Purpose: add the distinct `closed_recorded_qa_telemetry_fresh_restore` admission branch to frozen V10. It calls the V6 file-only verifier with exact old owner/restoration/initial-state bindings, requires its exact success status and preserved historical failure, and cannot fall through after a failed new verifier. V10's V5 and V4 recovery branches are retained verbatim.

Inputs and outputs remain the frozen capture plan, authorization, batch/attempt IDs and capture/ledger/restoration receipts. The owner authorization now needs27 canonical dependencies, including V4/V5/V6 recovery helpers and their READMEs. The unchanged supervisor bridge makes28 total. Historical producer copies remain nested under the corresponding recovery proof. Source review does not clear an unresolved owner or authorize a retry.

All capture/telemetry/transport behavior, initialization, gains, scientific controls,40GiB cap, C50/G75 floors,480 attempts,21600 charged seconds,60-second runner census and original deadline remain unchanged. V6 is a new failure-specific recovery gate; it does not change telemetry timeouts or current live source epochs.

PowerShell file-only check:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_capture_owner_v11.py" check-plan --plan 'CAPTURE_PLAN.json' --authorization 'CAPTURE_AUTHORIZATION.json'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_capture_owner_v11.py" check-plan --plan "CAPTURE_PLAN.json" --authorization "CAPTURE_AUTHORIZATION.json"
```

Only a separately reviewed root literal queue may call execute. V6 fake-service reproduction and exact recovery inputs are documented in README_S6D_CLOSED_TELEMETRY_RESTORE_V6.md. Original capture behavior remains documented in README_S6D_CAPTURE_V5.md and README_S6D_CAPTURE.md.
