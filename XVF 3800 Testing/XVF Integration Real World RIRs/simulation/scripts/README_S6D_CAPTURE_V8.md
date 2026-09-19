# S6D capture owner V8

`s6d_capture_owner_v8.py` is the preserved V7 owner with only its recovery helper and README dependency changed to `s6d_closed_telemetry_restore_v3.py` and README_S6D_CLOSED_TELEMETRY_RESTORE_V3.md. The same file-only recovery API, recovery.v2 schema/kind,24 canonical source bindings, actual OS listener preflight, telemetry V2, bridge V2 and normal restoration.v5 policy remain. Physical40GiB,480 attempts/21600 charged seconds and C50/G75GiB floors are unchanged.

Recovery V3 fixes the pre-restore getter seam only. It issues the exact ten Control.values queries plus raw BLD_MSG, accepts a single integer packed enum0 or1 before restoring, and validates the same firmware/microphone/build/DAC identity. The subsequent original-identity comparison is unchanged. Post-restore Control.identify still requires packed0. Original V1/V2 recovery failures and V6/V7 owner freezes remain preserved. See README_S6D_CLOSED_TELEMETRY_RESTORE_V3.md for that source's input schema and focused tests.

Inputs remain an exact root plan/authorization, fresh batch ID and literal attempt IDs. Authorization must bind the maintained V8 source, this README, V3 helper/README and the unchanged underlying execution sources. `reviewed_recoveries` contains exact binding records; a missing, ambiguous, mismatched or rejected recovery blocks ownership. V3 root source review status is ROOT_ACCEPTED_TELEMETRY_RECOVERY_V2_SOURCES_V3. Historical telemetry producer copies remain nested in the recovery's separate source review, avoiding duplicate basename snapshots in the owner's execution source list.

Outputs retain case source/configuration/audio/telemetry records, batch source epoch/SUMMARY/restoration and the physical ledger. The pre-lock host check still saves RECORDER_TCP_LISTENERS.json and its PASS/FAIL preflight decision; an incomplete/error/unknown table or matching recorder listener blocks before locking. Existing Python terminal persistence, STOP, callback, audio/telemetry/lease closure and exact static/immediate-gain/packed predicates remain mandatory. No source test or recovery receipt grants a queue launch by itself.

The narrow V3 fixture evaluates only the pinned Control.values/identify AST with fake query and saved V2 replies, then checks that the complete V8 source equals V7 after reversing only the declared dependency/doc names. It performs no hardware, live process census, locks, models or actual Control.query. Outputs are small reproduction and receipt JSONs on G. Choose a fresh suffix.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r="$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_closed_telemetry_restore_checks_v3.py" --source-root "$sim\scripts" --baseline-batch "$r\hardware_batches\bank_v2_P_MAIN6_B1" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v3\fresh_checks'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_checks_v3.py" --source-root "%SIM%\scripts" --baseline-batch "%R%\hardware_batches\bank_v2_P_MAIN6_B1" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v3\fresh_checks"
```

After root supplies a plan/authorization, file-only validation is `python -B s6d_capture_owner_v8.py check-plan --plan PLAN.json --authorization AUTHORIZATION.json`. Production remains the root-admitted runner's bridge V2 command with exact V8 owner/hash, plan/hash, authorization/hash, fresh batch and literal attempt IDs. It requires the runner's ownership/STOP/heartbeat environment; do not invoke it outside that admitted queue. README_S6D_CAPTURE_V5.md and README_S6D_CAPTURE.md retain the detailed capture/restoration contract.
