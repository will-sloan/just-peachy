# Fresh restore after closed native telemetry

V2 changes only the port-idle proof and its saved-file verification. V1's real attempt stopped before lock/getters/setters because Windows `connect_ex` returned an inconclusive10035. This does not establish an active recorder. V2 calls the complete OS `psutil.net_connections(kind='tcp')` census and never opens a test socket. Enumeration errors, partial or malformed tables, and unknown addresses/states fail closed. A LISTEN on8765,8766 or8767 bound to IPv4/IPv6 loopback, wildcard, or an IPv4-mapped loopback/wildcard blocks restoration. Other established connections and listeners on other ports remain distinguishable. Each census is saved before its decision, including a failing census, then bound into the successful checkpoint. The file-only verifier independently recomputes every listener decision. Current process scans, source/native checks, original settings, exclusive lease and exact restoration/policy behavior remain the V1 code paths. Original V1 source/review/FAILED_UNRESOLVED outputs are preserved. V2 requires a fresh root review and `closed_telemetry_restore_v2` output directory; V7 is the separately reviewed owner importing this helper.

`s6d_closed_telemetry_restore_v2.py` is a separately admitted recovery for the failed `bank_v2_P_MAIN6_B1` owner. The original failure reports closed audio and a released lease, but unproven Python telemetry closure. Native `result.json` reports successful cleanup, all14 pending reads false, and a complete2381-row measurement population in native samples, stdout and the received journal. The helper verifies these exact files, preserves the absence of the Python terminal receipt and does not invent the old telemetry PID or termination cause.

This helper performs no import-time device or process operations. `inspect-inputs` is file-only. `execute` is a real restoration operation reserved for root after source/fixture review and explicit input authorization. It never opens audio playback/capture streams, starts telemetry, terminates a process, changes the original ledger or rewrites old failed receipts. It does issue fresh device getters, a packed-input-disable setter, an original-width reset when required, and the existing exposed-setting restoration under the hardware lock. It must not be treated as the old gain-only/getter-only recovery.

## Required root review input

Both CLI actions require `--source-review PATH --source-review-sha256 SHA256`. The JSON contains:

- `status`: `ROOT_ACCEPTED_TELEMETRY_RECOVERY_V2_SOURCES_V2` for execution; file-only inspection also accepts `PROPOSED_SOURCE_REVIEW_ONLY`.
- `allow_fresh_exposed_restore`: true for execution; false in a proposal.
- `run_id`: `20260913T195357Z`; `owner_thread_id`: `01a0812d-3ff0-7ed0-a06c-4df61b62a459`.
- `original_batch`: `bank_v2_P_MAIN6_B1`; `recovery_kind`: `closed_native_telemetry_fresh_restore`.
- `source_bindings`: exact `{path,bytes,sha256}` records covering this helper/README, accepted pureV5 policy, `s3_hardware.py`, `s4_restore.py`, `s4_common.py`, `s0_common.py`, measurement_app core/init, host EXE/DLLs, and the failed attempt's four preserved telemetry producer files. Additional reviewed loggerV2/ownerV6 files may be included.
- `original_bindings`: `ledger,owner,restoration,initial_state,bridge_failure,supervisor_launch,admission,summary` exact bindings. The persisted bridge/launch supply owner/supervisor PID plus creation time; no historical telemetry PID record is required.
- `root_process_snapshot` and `output_confirmation`: bound initial root census and confirmed disconnected XVF analog outputs. The old census is supplementary; current checks are repeated during execution.
- `telemetry_bindings`: `native_result,native_inspection,native_samples,native_transactions,stdout,received,stderr` exact files for S45_01_17's failed telemetry folder.
- `expected_measurement_rows`:2381; `historical_telemetry_pid_creation`:null.
- `recovery_output_root`: one exact, fresh recovery directory under this S6D report.

The required source list is returned by the pure `required_sources()` function. Every file is rehashed; the full ledger is copied byte-for-byte into an immutable recovery snapshot so later ledger growth does not invalidate the historical evidence. All old failed captures/charges remain original facts.

## Execution and failure behavior

The helper verifies native cleanup, exact14 field counts, all native/stdout/received payloads and sequence numbers, the terminal native stdout result, every transaction/retry count and pending terminal responses, and empty stderr. It never substitutes these for a historical Python manager result.

Before any getter, it scans all current process command lines, checks original owner/supervisor PID+creation absence, checks recorder ports8765–8767, acquires the existing exclusive hardware lock, then repeats source/input/process/port checks. Unreadable critical interpreter/control processes block. Only its exact current PID is excluded. Even another parent shell that still contains a control command may conservatively block; use a root-owned launcher that exits, rather than weakening the scan. PID reuse is recorded and an unrelated reused PID is not killed. The original telemetry PID was not persisted, so the full command-line scan covers that missing identity.

Under the lock it verifies current immutable device identity, repeats process/port checks immediately before setters, writes durable `RESTORE_STARTED.json`, then calls the unchanged accepted `set_verified(I2S_INPUT_PACKED,[0])`, `reset(original_USB_width, change_width=...)`, and `restore_exposed(original_settings)`. A complete fresh identity/static/ancillary readback is evaluated by the unchanged pureV5 policy. Current AGC drift is allowed only under that exact policy; no static or identity tolerance is added. The native process scan repeats after restoration. The lock must be released successfully before a recovery PASS is written.

Failures preserve `RESULT.json` with `FAILED_UNRESOLVED` when writing remains possible; `RESTORE_STARTED.json` remains an honest record that a fresh restore was attempted. No recovery PASS is published on scan, getter/setter, policy, source-binding, port or lock-release failure. The helper never clears an old supervisor hardware guard or supplies a new queue approval. Root must explicitly review the actual new recovery, update admission, and run fresh QA as separately requested.

Outputs are process-snapshot JSONs, per-stage `*_TCP_LISTENERS.json`, `ORIGINAL_LEDGER.json`, command logs from unchanged Control, durable `RESTORE_STARTED.json`, `RESULT.json`, and only on verified success `RECOVERY.json`. The recovery has `schema_version=edge-s6d-restoration-recovery.v2` and the distinct recovery kind above. It binds the **fresh** reapply/readback/result, current native/process/listener closure and released lock. `no_playback=true`, but `no_setters_or_reset=false`; original telemetry closure and historical Python terminal receipt remain false. V5 intentionally refuses this new recovery kind; separately reviewed V7 admission must call this helper's `verify_recovery_record`.

## Run

PowerShell, file-only inspection (safe before root execution approval):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$sim\scripts\s6d_closed_telemetry_restore_v2.py" inspect-inputs --source-review '<exact root review or proposal.json>' --source-review-sha256 '<SHA256>'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_v2.py" inspect-inputs --source-review "<exact review.json>" --source-review-sha256 "<SHA256>"
```

After root's explicit actual restore admission, use the identical command with `execute` replacing `inspect-inputs`; keep the literal approved review/hash and fresh output in that review. The source-writing/review agent must not invoke `execute` or create current process/device evidence. No periodic retries, auto-recovery loop or unreviewed fallback is installed.

File-only V7 API: `verify_recovery_record(receipt, owner_binding=..., restoration_binding=..., initial_binding=...)` returns a proof or raises. It rechecks stored source/root authority, original immutable ledger/owner/state, native populations, saved process and OS TCP listener decisions, fresh restore/policy and release flags. It does not run a process scan or touch hardware. Current process closure must also be enforced by the new owner before its new hardware work.

## Narrow V2 fixtures

`s6d_closed_telemetry_restore_checks_v2.py --output FRESH_G_DIRECTORY` tests synthetic IPv4/IPv6 loopback, wildcard, mapped-address, nonlistener and unrelated-port rows; enumeration errors and malformed snapshots; before-lock and under-lock fail-closed ordering; and saved census evidence. `--actual-read-only` additionally performs one explicitly requested read-only OS TCP census and verifies the existing2381-row native file population. It performs no live process census, lock acquisition, device or model call. Output is a compact receipt plus synthetic failure evidence, and optional read-only TCP/native proofs, all on G.

PowerShell: `& $py -B "$sim\scripts\s6d_closed_telemetry_restore_checks_v2.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v2\fresh_checks' --actual-read-only`.

Anaconda Prompt / CMD: `"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_checks_v2.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v2\fresh_checks" --actual-read-only`.

The V1 fixture section below describes preserved historical checks against V1. Do not run it against V2's changed service return schema; V2 has the targeted suite above.

`s6d_closed_telemetry_restore_checks_v1.py --output FRESH_G_DIRECTORY` uses tiny synthetic native journals and fake process/port/lock/device services. It tests fail-closed data/admission/ownership ordering and fresh-restore records without calling WindowsServices. It writes local fixture receipts only. PowerShell: `& $py -B "$sim\scripts\s6d_closed_telemetry_restore_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v1\fresh_checks'`. Anaconda/CMD: `"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v1\fresh_checks"`. Preserve existing outputs and choose a new suffix for a changed run.

Optional `--helper EXACT_SOURCE.py` selects an independently copied source for review. `--actual-native-files-read-only` additionally checks the seven original failed-attempt telemetry files and writes their proof into the fresh G fixture directory; it performs no process/device queries. The suite contains33 synthetic groups plus this optional actual-file group. Its production-verifier positive test substitutes the authority/result **in memory only**; no fake root acceptance or nonfixture recovery is written. All on-disk recovery fixtures are explicitly `fixture_only=true` and production admission rejects them. The first fixture run's changed-payload case accidentally aliased the received and native value lists; that failed fixture receipt is retained, and the corrected fixture makes independent copies without changing its rejection assertion.
