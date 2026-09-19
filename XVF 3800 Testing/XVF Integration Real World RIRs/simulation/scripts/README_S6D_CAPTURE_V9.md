# S6D capture owner V9

`s6d_capture_owner_v9.py` is the preserved V8 owner with only its recovery helper and README dependency changed to `s6d_closed_telemetry_restore_v4.py` and README_S6D_CLOSED_TELEMETRY_RESTORE_V4.md. The same file-only recovery API, recovery.v2 schema/kind,24 canonical source bindings, actual OS listener preflight, telemetry V2, bridge V2 and normal restoration.v5 policy remain. Physical40GiB,480 attempts/21600 charged seconds and C50/G75GiB floors are unchanged.

Recovery V4 admits either complete exact original identity or complete exact recorded failed17 configured identity, bound through original admission/plan and the immutable failed ledger row. Only the documented five mutable fields are projected; all other identity fields stay exact. Post-restore Control.identify still requires packed0 and the original restoration policy. Original V1/V2/V3 recovery failures and earlier owner freezes remain preserved. See README_S6D_CLOSED_TELEMETRY_RESTORE_V4.md for the required failed_configuration input and full orchestration fixtures.

Inputs remain an exact root plan/authorization, fresh batch ID and literal attempt IDs. Authorization must bind the maintained V9 source, this README, V4 helper/README and the unchanged underlying execution sources. `reviewed_recoveries` contains exact binding records; a missing, ambiguous, mismatched or rejected recovery blocks ownership. V4 root source review status is ROOT_ACCEPTED_TELEMETRY_RECOVERY_V2_SOURCES_V4. Historical telemetry producer copies remain nested in the recovery's separate source review, avoiding duplicate basename snapshots in the owner's execution source list.

Outputs retain case source/configuration/audio/telemetry records, batch source epoch/SUMMARY/restoration and the physical ledger. The pre-lock host check still saves RECORDER_TCP_LISTENERS.json and its PASS/FAIL preflight decision; an incomplete/error/unknown table or matching recorder listener blocks before locking. Existing Python terminal persistence, STOP, callback, audio/telemetry/lease closure and exact static/immediate-gain/packed predicates remain mandatory. No source test or recovery receipt grants a queue launch by itself.

The narrow V4 fixture executes full recovery orchestration with actual original/configured metadata and fake services, then checks that the complete V9 source equals V8 after reversing only the declared dependency/doc names. It performs no hardware, live process census, locks, models or actual Control.query. Outputs are small reproduction and receipt JSONs on G. Choose a fresh suffix.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r="$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_closed_telemetry_restore_checks_v4.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v4\fresh_checks'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_checks_v4.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v4\fresh_checks"
```

After root supplies a plan/authorization, file-only validation is `python -B s6d_capture_owner_v9.py check-plan --plan PLAN.json --authorization AUTHORIZATION.json`. Production remains the root-admitted runner's bridge V2 command with exact V9 owner/hash, plan/hash, authorization/hash, fresh batch and literal attempt IDs. It requires the runner's ownership/STOP/heartbeat environment; do not invoke it outside that admitted queue. README_S6D_CAPTURE_V5.md and README_S6D_CAPTURE.md retain the detailed capture/restoration contract.
