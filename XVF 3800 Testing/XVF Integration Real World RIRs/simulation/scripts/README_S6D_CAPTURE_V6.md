# S6D capture owner V6

`s6d_capture_owner_v6.py` adds the separately reviewed telemetry V2 logger and a distinct fresh-restoration recovery admission branch to preserved V5. `s6d_capture_checks_v6.py` runs narrow file-only recovery dispatch checks on G. All original failed attempts, missing Python terminal evidence and restoration FAIL receipts remain unchanged. Source/model-free acceptance alone does not qualify real telemetry or authorize playback.

The fourteen telemetry fields, rates, native C#/PowerShell, source gain/RIR/PCM, DSP settings including the GAIN setter, callback buffering, STOP delivery, attempt charges and existing transport/restoration gates remain. Limits remain 480 physical attempts, 21,600 charged seconds, 40 GiB payload, C free >=50 GiB and G free >=75 GiB after allocation. See README_S6D_TELEMETRY_V2.md for explicit native terminal-frame versus EOF proof, original finite deadlines, persisted PID/creation/lifecycle/failure and cooperative-stop-only behavior. V6 also requires `terminal_receipt_persisted=true` before competing control can resume; failure SUMMARY retains the returned telemetry result or the fact that wait returned nothing.

Inputs are the exact root plan, source-bound authorization, fresh batch ID and literal attempt IDs. Authorization uses the existing `reviewed_recoveries: [{path, bytes, sha256}, ...]`. Every old unclosed owner blocks unless exactly one matching explicitly listed recovery proves closure. Existing recovery.v1 remains gain-only, getter-only, and requires original telemetry/audio/lease closure. It cannot close the S45_01_17 missing Python receipt.

Only `edge-s6d-restoration-recovery.v2` takes the new branch. The pure `s6d_closed_telemetry_restore_v1.verify_recovery_record` validates its `closed_native_telemetry_fresh_restore` kind, root source authority, exact original owner/restoration/initial state, immutable old ledger snapshot, original native cleanup/rows, recorded process closure, fresh actual restore/result, recomputed policy and lock release. The owner requires the explicit verified proof and preserved old failure. It does not run the recovery helper's getters, setters, process census or locks. That root-only recovery operation and its separate source review are documented in README_S6D_CLOSED_TELEMETRY_RESTORE_V1.md. Ledger growth cannot replace the immutable original recovery evidence.

Source authorization adds V6, this README, telemetry V2 and its README, the recovery helper and its README. Keep V5 policy/README, transport, C#/PowerShell, underlying hardware/restoration sources and official binaries bound. Maintained script paths are the execution authority; frozen copies are review evidence. Normal restoration outputs retain `edge-s6d-restoration.v5` and the unchanged pure dynamic-gain policy. Therefore accepted bridge V2 remains applicable; no separate bridge README is needed. Its explicit exact-static, immediate-gain, packed-disabled, same-owner, telemetry/audio/lease, observer and STOP checks remain mandatory.

Outputs retain native/derived audio, per-attempt telemetry and result, batch source epoch/SUMMARY/restoration and ledger. Telemetry V2 adds identity/lifecycle/terminal-failure and optional diagnostic-only late closure files. Model-free fixtures write small synthetic failed-owner/recovery trees and RECEIPT.json. Their positive dispatch verifier is explicitly mocked; actual verifier rejects fixture/wrong-kind records. They never create actual root authority, recover hardware, launch a process or promote old FAIL.

Run bounded fixtures in the existing Anaconda environment (numpy and psutil). Choose a fresh G suffix.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r="$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_capture_checks_v6.py" --source-root "$sim\scripts" --baseline-batch "$r\hardware_batches\bank_v2_P_MAIN6_B1" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\capture_v6\checks_v1'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_capture_checks_v6.py" --source-root "%SIM%\scripts" --baseline-batch "%R%\hardware_batches\bank_v2_P_MAIN6_B1" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\capture_v6\checks_v1"
```

After root supplies actual plan/authorization, read-only validation is `python -B s6d_capture_owner_v6.py check-plan --plan PLAN.json --authorization AUTHORIZATION.json`. It verifies files and does not establish current hardware safety.

Production remains the root-admitted runner's literal bridge command: `s6d_capture_supervisor_bridge_v2.py --owner <maintained V6 path> --owner-sha256 <reviewed hash> --plan <exact plan> --plan-sha256 <hash> --authorization <root authorization> --authorization-sha256 <hash> --batch <fresh ID> --attempt-ids <exact IDs>`. Run only with the runner's required ownership/STOP/heartbeat environment. The prospective continuation must preserve the sixteen already captured MAIN passes, repeat failed seventeen as a fresh ID, and perform fresh pre-QA under root admission; these source files do not create that queue, waive batch/post-QA closure, or grant permission to execute it.
