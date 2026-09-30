# Transport output and TRACE adapters V1

Purpose: integrate explicit GroupWriter limits into actual retained isolated transport child owner/ready/result writes and a fresh retained TRACE wrapper, preserving socket closure and explicit failure accounting. No capture, hardware, models or GUI. The only allowed source factory is the bound empty/wait fixture. The original transport frame loop and terminal/ACK mechanics are retained byte-for-byte; no unchanged audio-protocol sweep. All source bytes, retained selected installed dependencies, allocation, authority and fresh census bind through the admission.

`field_transport_outputs_v1` validates an exact config schema, capture=false, fixture factory/mode, admission/source/plan hashes, same-boot absolute deadline and six group budgets no greater than V2. Its seven-directory layout checks actual metadata+64KiB growth against1MiB/128directories. These checks cover the selected layout, not every future archive or host directory. Named CHILD_OWNER/CHILD_READY/CHILD_RESULT use source; CONFIG uses config; independent parent REGISTERED_OWNER uses control; rejected exact payloads and bounded diagnostics use failure; TRANSPORT_CLOSURE uses closure_reserve. Failure names include PID+sequence. GroupWriter limits count old+pending writes. Existing evidence is never overwritten/retried/deleted; failures remain explicit.

`isolated_source_transport_budget_v1` creates the socket before receipt publication and always closes it after terminal/result processing, including result quota failures. Parent registers exact PID/start ticks before sending a handshake permitting child work. This registration remains available if the child owner publication itself rejects. A non-daemon watcher runs the existing absolute-deadline supervisor concurrently with parent blocking work; child has the same deadline alarm. Parent finalization checks child exit and reserved closure; terminal ACK alone is not success. Child always attempts stop and close separately. Missing closure after SIGKILL is reported as missing, never reconstructed as logical completion. No arbitrary parent-process/GIL freeze, OS scheduling deadline, descendants or hardware-cleanup guarantee.

`field_trace_accept_v1` extracts the retained traced_accept wrapper into a bound adapter. First and later writes all use the same pre-write guard. The original accept happens first; on TRACE/sample-limit failure the real retained pipeline _error sets failure and requests Stop while preserving already accepted sample counts. It does not throw that accepted block into _run's rejected-block count a second time. Tests use a counted original-accept stub and two temporary generated float32 zeros, storing hashes only; they do not qualify actual journal/timing/accepted-tail passage or microphone silence. Full installed pipeline/controller integration remains pending.

Nine native cases: five real child-process transports (normal, owner quota, ready quota, result quota, parent blocked past deadline) and four TRACE/error adapters (normal, first-write reject, append reject, accepted-sample ceiling). Transport carries zero blocks/samples. First four children use10s total/2s grace within60s/2s admission; blocked parent uses1.2s/.3s and sleeps1.5s while watcher remains active. Forced kill has no logical result/closure; exact owner and terminal evidence stay private. Four expected child failures, not five successful logical recordings. Real child limits256MiBAS; parent768MiBAS; shared CPU2/3/200%,Tasks64,1MiBstacks,300s parent/60s service Stop/32MiB per-file. Initial850MiB available/sample192MiB available/640MiB aggregate stops. Admission4MiB target+4MiB host; fixed32GB/5GiBfree. Current WINDOW_V5/52GiB total including retained2.5GiB reservations and5GiB output unchanged.

Inputs: fresh CPU14 census, exact staged code/config/allocation/authority and retained v12 selected module hashes. Outputs: fresh field-transport-outputs-v1 target and field-transport-outputs-v1-evidence private host folder; config/owner/terminal/closure/diagnostic/case/RESULT/resource receipts and exact backup. No release/catalogue/asset/runtime/audio copy. Existing source V75 adapters and old factories remain unchanged. This is no-capture qualification, not a production/capturable factory. Entry/live config, GUI presentation, outer logs/resources/RESULT/staging/host backup and full directory counts still require complete integration/allocation.76MiB target+80MiB host remains unadmitted. All new code is documented here, source-reviewed/compiled as UTF8 bytes before staging, and immutable after admission.

## PowerShell

Run once. Census under15minutes is required; preserve old numbered receipts. Do not rerun a bound completed/failing target.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,8*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V169.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_transport_outputs_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V169.json'
& $py -B review_field_transport_outputs_v1.py
& $py -B backup_field_transport_outputs_v1.py
& $py -B collect_native_closure_v5.py --version 168
```

## Command Prompt / Anaconda Prompt

Use the existing interpreter explicitly; no activation/download/install. If the census above already exists, do not recreate it. To create a fresh numbered census, run the same -B -c Python command with the full quoted interpreter instead of & $py.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_transport_outputs_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V169.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_transport_outputs_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_transport_outputs_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 168
```

Internal --child-fd/config/config-sha256 and dispatcher --gate/--worker are only source-bound protocol plumbing, not GUI flags. Recovery preserves failed output and requires a separate reviewed derivative/admission, never a retry. Original app/config/personal data are untouched; closure verifies unchanged identities/hashes and free capture/research/hardware leases. Raw artifacts stay private.
