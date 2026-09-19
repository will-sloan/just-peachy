# Cheap status for the five continuous sessions

Purpose: read only the serial long dispatcher's immutable admission, latest readable immutable heartbeat/result and exact prepared queue. It never opens the original C RESOURCE_HEARTBEAT.json or B36 HEARTBEAT.json, native logs, audio, events or model files. No launch, process termination, lease mutation or authority creation occurs.

Inputs: REPORT root (defaults to the current S6C report), exact namespace `five_prepared_long_v1`, and optional QueuePath (defaults to REPORT/serial_long_dispatcher/preparation_v1/QUEUE.json). The admitted queue must contain C065/C067/C088/C091/B36 in that order. It reads file handles with ReadWrite/Delete sharing, binds the queue buffer to the actual dispatcher admission, and reports session counts rather than canonical scenes.

Output: one JSON status on stdout, with snapshot path/time, completed/requested sessions, active item, dispatcher/child process observations, result-read errors and lease presence. A missing dispatcher directory means prepared but not started; a directory without admission remains unavailable. An incomplete/temporarily unreadable newest snapshot falls back to an older readable immutable snapshot, with skipped count and original timestamp. It checks at most20 blocks of1000 snapshot names and reads only until one valid snapshot is found. In normal use it reads one newest snapshot. Never infer completion from a stale heartbeat or a missing PID. PowerShell creation-time comparison retains the original status-reader50ms tolerance and is explicitly observational; exact Python owner/native/lease admission is separate.

This is a narrowly scoped descendant of s6c_paced_status_v3.ps1: shared read access and cheap .NET owner observations are retained; mutable child heartbeat reads are removed; long queue/path/status semantics are explicit. The original reader is unchanged. test_s6c_serial_long_status_v1.py shares this README and creates only private JSON fixtures, invoking the reader through hidden PowerShell with no native/model work.

PowerShell:

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$simRoot\scripts\s6c_serial_long_status_v1.ps1"
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$simRoot\scripts\test_s6c_serial_long_status_v1.py" --output "$simRoot\reports\S6C\20260910T123540Z\serial_long_dispatcher\status_source_checks_v1"
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File s6c_serial_long_status_v1.ps1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_serial_long_status_v1.py --output "..\reports\S6C\20260910T123540Z\serial_long_dispatcher\status_source_checks_v1"
```

Use a fresh test output for reproduction. Runtime reading writes nothing. An optional `-ReportRoot` and `-QueuePath` point to private test metadata; runtime should use the exact defaults above.
