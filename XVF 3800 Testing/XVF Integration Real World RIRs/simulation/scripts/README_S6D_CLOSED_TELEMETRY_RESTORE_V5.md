# Recorded telemetry failure recovery V5

`s6d_closed_telemetry_restore_v5.py` handles only the preserved `bank_v3_P_MAIN6_B3` / `P_MAIN6_S45_04_19` failure. Its Python terminal receipt explicitly records FAIL, native process exit and stderr closure unproven, although the exact native terminal, cleanup, all 14 pending flags and all 2,390 received measurement rows are verified. This differs from the earlier failure that had no Python terminal receipt. V1–V4 and every actual failure/charge remain unchanged.

The recovery schema remains `edge-s6d-restoration-recovery.v2`; its distinct kind is `closed_recorded_telemetry_fresh_restore`. The required root source status is `ROOT_ACCEPTED_RECORDED_TELEMETRY_RECOVERY_V5_SOURCES_V1`. Source review does not itself restore the device. Execution requires `allow_fresh_exposed_restore=true`, the exact root thread/run/batch, fresh output under the campaign report, and every bound input below.

Inputs are `source_bindings` covering `required_sources()`; `original_bindings` for owner, restoration, initial_state, admission, summary, ledger, bridge_failure, supervisor_launch, failed_configuration and failed_capture_metadata; the root's bound `root_process_snapshot` and `output_confirmation`; `expected_measurement_rows=2390`; and `historical_telemetry_pid_creation` with PID609852 and creation1789410880.3176687. `telemetry_bindings` has native_result, native_inspection, native_samples, native_transactions, stdout, received, stderr, python_terminal, process_identity, lifecycle and late_reader_closure. These are the exact files under the failed04_19 telemetry folder. The preserved recorded identity binds its parent, argv, producer and libraries; the owner summary must contain the exact terminal FAIL.

The preliminary root snapshot is a required source input, not current process-closure authority. The executing helper freshly enumerates complete process command lines and OS TCP listeners before locking, again under the hardware lock before getters, immediately before setters and after restoration. The recorded telemetry PID/creation joins the old owner and supervisor identities. Matching task-control processes, opaque interpreter identities, any loopback/wildcard recorder listener, incomplete enumeration or lock failure block restoration. There is no termination, timeout-as-idle inference or automatic retry.

The unchanged V4 identity gate accepts the complete exact original identity or the complete recorded configured identity, never a mixture. The actual restore retains packed0 verified setter, original USB reset, `restore_exposed`, full readback and the accepted pure V5 policy. Device, firmware, static/ancillary and USB checks stay strict. Original audio/writer closure and the charged failed attempt/source/configuration are bound before setters. No audio is opened and no capture is promoted.

Outputs are immutable original-ledger snapshot, process/TCP evidence, commands, RESTORE_STARTED, RESULT and only after verified restoration plus released lock, RECOVERY. The recovery records historical Python receipt present but original telemetry process closure false. It never supplies a historical exit time or explains the unrecorded host shutdown delay. `verify_recovery_record(receipt, owner_binding=..., restoration_binding=..., initial_binding=...)` is file-only and returns `VERIFIED_CLOSED_RECORDED_TELEMETRY_FRESH_RESTORE`; ownerV10 uses this exact branch without fallback to old recovery kinds. New queue admission remains separate.

PowerShell file-only input inspection after root supplies the actual review:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_closed_telemetry_restore_v5.py" inspect-inputs --source-review 'REVIEW.json' --source-review-sha256 'EXACT_SHA256'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_closed_telemetry_restore_checks_v5.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v5\checks_v1'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_v5.py" inspect-inputs --source-review "REVIEW.json" --source-review-sha256 "EXACT_SHA256"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_checks_v5.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v5\checks_v1"
```

Use a fresh G fixture suffix. The fixture reads saved actual metadata/telemetry, uses fake services with the actual retained restoration method, and writes only fixture receipts. It tests the new terminal/identity/source/lifecycle joins, historical-failure preservation, recorded PID exclusion, original/configured restore, mixed-state refusal, pure verifier and ownerV10 dispatch. It does not enumerate processes or TCP, load control services, touch a device or create root approval. Root alone may replace `inspect-inputs` with `execute` against the exact reviewed source and actual fresh-restoration authority; intended output is `R/closed_telemetry_restore_v5`.
