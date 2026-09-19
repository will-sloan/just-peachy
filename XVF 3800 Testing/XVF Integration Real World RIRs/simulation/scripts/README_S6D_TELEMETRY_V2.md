# S6D telemetry V2: explicit terminal lifecycle

`s6d_telemetry_v2.py` is an additive opt-in logger with the same constructor/start/ready/healthy/stop/wait interface as the preserved V1. The V1 S45_01_17 failure remains unchanged. A model-free real-pipe fixture reproduced V1's reader-join early return, which can omit both result.json and the done signal even after a later EOF. The historical run did not log enough process/thread lifecycle detail to prove that this exact branch caused its failure.

V2 keeps all fourteen fields, rates, native C#/PowerShell source, requested duration,8-second cooperative-stop budget, duration+20-second deadline,3-second process wait and3-second reader drain. No kill/terminate is issued to any hardware/control process. A deadline writes cooperative stop and persists explicit unproven-closure failure. Owner V6 must refuse competing commands on that failure.

The buffered reader retains the64KiB line cap, all native payload/QPC transaction fields and one actual host monotonic line-consumption timestamp per row. It recognizes the adapter's final JSON summary only when it exactly matches native/result.json and every received per-field count. C# writes this after cleanup and after closing native journals. This explicit protocol terminator allows the reader to close its own pipe without waiting for EOF held elsewhere. `actual_stdout_eof` and `verified_native_terminal_frame` are distinct. Natural process exit, code0, closed reader/files, exact terminal/native evidence, all14 pending flagsfalse and cleanup_return0 are still mandatory for control closure; scientific PASS additionally requires native PASS, matching DLL/count evidence, empty stderr and no errors. Missing/mismatched summaries fail closed. Buffered host-consumption times are not identical historical V1 timings; native QPC transaction bounds are preserved byte-for-byte and no DSP clock is invented.

Inputs are the existing official DLL directory, fresh G attempt telemetry directory, finite duration and frozen14-field rates. `start` is invoked only by the admitted hardware owner. Outputs add PROCESS_IDENTITY.json (child/parent PID+creation, argv/source/library bindings) and append-only lifecycle.jsonl to original stdout.bin/received_telemetry.jsonl/stderr.bin/native outputs. `result.json` is a terminal decision even for an unclosed process/reader. `wait()` can therefore return explicit FAIL promptly. A later reader close writes separate diagnostic-only late_reader_closure.json, never rewrites/promotes FAIL and never authorizes recovery. If terminal persistence itself fails, the returned result is FAIL with control closurefalse and terminal_receipt_persistedfalse; owner must retain that failure detail. Native PASS alone is insufficient.

`s6d_telemetry_checks_v2.py` exercises real anonymous pipes and fake processes only. It verifies exact decoded rows/QPCs with buffered reads, terminal-frame versus EOF, delayed EOF, missing/mismatched/oversized records, process/reader timeout diagnostics, no termination calls and late-close failure preservation. It creates no process, imports no vendor DLL and issues no audio/device/model calls.

PowerShell, choose a fresh G suffix:

```powershell
$s='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$attempt='G:\Just_Peachy_S6D\20260913T195357Z\bank_captures_v1\beam_bank\S45_01_17\P_MAIN6\P_MAIN6_S45_01_17'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s\s6d_telemetry_checks_v2.py" --source "$s\s6d_telemetry_v2.py" --saved-attempt $attempt --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\telemetry_v2\checks_v1'
```

Anaconda Prompt / CMD:

```bat
set "S=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set "ATTEMPT=G:\Just_Peachy_S6D\20260913T195357Z\bank_captures_v1\beam_bank\S45_01_17\P_MAIN6\P_MAIN6_S45_01_17"
"C:\Users\amiri\anaconda3\python.exe" -B "%S%\s6d_telemetry_checks_v2.py" --source "%S%\s6d_telemetry_v2.py" --saved-attempt "%ATTEMPT%" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\telemetry_v2\checks_v1"
```

The fixtures also exercise the real `start()` method with Popen and process identity lookup replaced by fake functions, verifying buffered argv, persisted PID/creation and launch-failure settlement without launching any child. Captured identity must be persisted and the reader thread must actually finish before control closure. Integer counts reject booleans even though Python normally compares True equal to 1. Prior checks_v1/v2 remain historical intermediate fixtures; select a fresh suffix for every rerun.

Existing Anaconda requires numpy and psutil. The logger has no standalone production CLI. Future production uses exact reviewed owner V6 and its root-admitted plan/bridge command; do not instantiate this logger outside hardware ownership. Source review/model-free tests are not physical telemetry qualification or restoration. The original source/gain/profile/cap/floor contracts remain required.
