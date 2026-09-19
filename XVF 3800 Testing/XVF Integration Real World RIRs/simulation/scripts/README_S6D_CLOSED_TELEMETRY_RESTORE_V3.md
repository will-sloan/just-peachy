# Recovery V3: read-only identity before restoring packed mode

`s6d_closed_telemetry_restore_v3.py` preserves V2's source/native population, process census, complete TCP-listener census, exclusive hardware lease, fresh restore and pure restoration-policy checks. It changes only the WindowsServices pre-restore identity getter. Actual V2 stopped with `FAILED_UNRESOLVED` after eleven successful getters because the existing `Control.identify()` requires packed input0; the failed capture had correctly left packed input1 pending recovery. No V2 setters began and its lock was released. Its source and actual failed receipts remain unchanged.

`pre_restore_identity(control)` issues the same ten ordered `Control.values` queries and raw `BLD_MSG` query as the pinned Control.identify. It validates firmware3.2.1, linear array, four microphones, expected build and DAC0, and accepts only a single integer packed enum0 or1. It neither sets nor normalizes any device value. Query errors and invalid enums fail closed. The existing subsequent comparison to the original identity, except USB width and packed input, remains unchanged. Post-restore `Control.identify()` still requires packed0 and DAC0; no post-restore condition is relaxed.

Inputs retain the exact root source review, failed batch/source/telemetry bindings, explicit analog-output confirmation, original immutable ledger and fresh output path. The root execution status is `ROOT_ACCEPTED_TELEMETRY_RECOVERY_V2_SOURCES_V3`; the intended new output is `R/closed_telemetry_restore_v3`. `required_sources()` binds this V3 helper/README plus unchanged underlying dependencies. Same file-only API: `verify_recovery_record(receipt, owner_binding=..., restoration_binding=..., initial_binding=...)`; same `edge-s6d-restoration-recovery.v2` and `closed_native_telemetry_fresh_restore` kind. Owner V8 changes only its V7 dependency/README bindings to V3. Physical40GiB policy and all other limits are unchanged.

Outputs are the inherited process/TCP snapshots, exact command logs, immutable ledger snapshot, RESTORE_STARTED and RESULT, plus RECOVERY only on actual verified restore and released lease. The old missing Python telemetry receipt remains false. V3 does not clear guards or grant a new queue admission. See README_S6D_CLOSED_TELEMETRY_RESTORE_V2.md for the complete retained input schema and lifecycle; use V3's names/status and a fresh output, preserving V1/V2 failures.

The narrow `s6d_closed_telemetry_restore_checks_v3.py` reads the pinned Control source (SHA8388988d…) and saved eleven V2 stdout replies. It evaluates only the actual `values` and `identify` AST methods with a fake read-only query, reproduces packed1 rejection, checks V3's identical getter sequence, invalid states/read failures and unchanged strict post-restore/lifecycle code. It imports no measurement_app module or live query implementation. No process census, locks, device or model calls occur. Fixture outputs are small reproduction/identity/receipt JSONs on G.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r="$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_closed_telemetry_restore_checks_v3.py" --source-root "$sim\scripts" --baseline-batch "$r\hardware_batches\bank_v2_P_MAIN6_B1" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v3\checks_v1'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_checks_v3.py" --source-root "%SIM%\scripts" --baseline-batch "%R%\hardware_batches\bank_v2_P_MAIN6_B1" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v3\checks_v1"
```

Choose a fresh output suffix. After root provides an exact reviewed source/input JSON, file-only inspection is `python -B s6d_closed_telemetry_restore_v3.py inspect-inputs --source-review REVIEW.json --source-review-sha256 SHA256`. Root alone may replace `inspect-inputs` with `execute` after explicit source and actual restoration admission, using the recorded fresh output. This source-writing task does not run either hardware restoration or automatic retries. Existing runtime dependencies remain those documented for V2.
