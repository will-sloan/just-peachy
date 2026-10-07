# Native private storage scenario

`native_storage_check.py` verifies the many-session storage behavior using
synthetic private fixtures. It captures no microphone audio, imports no model,
does not open a GUI, and does not inspect or modify the operator recording store.
`launch_storage_check_action.py` prepares the same owned finite job/monitor
schema as the raw and pipeline actions. Neither has been run natively by the
host checks documented here.

## Inputs and outputs

The injected action payload contains the exact immutable package path and
`package_manifest_sha256`, current `boot_id`, expiry at most600 seconds ahead,
fresh label `storage-check-NN`, and `maximum_output_bytes: 16777216`. Existing
`host_operations.py` must first verify current ownership/leases and independent
PC C:50GiB/G:75GiB reserves plus this output allocation. Native admission keeps
the deployment's free-space floor plus another independent16MiB allocation.

The shared wrapper verifies all package bytes and its actual MainPID,
InvocationID, cgroup, CPU2/3,200% quota and TasksMax64 before invoking the harness.
It registers its real owner before project reads, holds the exclusive research
lease, never acquires the microphone lease, and runs at most180 seconds with
30-second service Stop. The harness registers its owner, selects CPU3 and
narrows to128MiB address space,1MiB stack and16MiB per-file limit. Existing
allocator variables are inherited before execution. No native limit is raised.

All fixtures are created under exactly:

```text
/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/storage-check-NN/storage-check/fixtures
```

The root must be fresh and canonical.31 kept recordings receive unique IDs,
are reopened and read across five7-row History pages, and retain authoritative
sample counts. The scenario reads one complete recording through bounded
chunks, exports one and multiple selected recordings, rejects unconfirmed
deletion, deletes only the selected private fixture, and verifies an unrelated
sentinel survives. Four further private fixtures exercise cancelled/failed
receipts, explicit post-Stop discard, and successful admission afterward;
35 sessions are created in total. No global recording slot is used. The data
and exports remain for independent monitoring/readback; no automatic broad
cleanup runs.

Outputs include the standard `JOB.json`, `OWNER.json`, `UNIT_OWNERSHIP.json`,
bounded wrapper logs and durable `JOB_EXIT.json`; the harness adds
`REGISTERED_OWNER.json` and `STORAGE_RESULT.json`. The ordinary native monitor
must prove exact owner/cgroup closure and independently copy the complete output.
The result proves storage operations on synthetic data, not acoustic replay
quality, raw qualification, touch interaction or model throughput.

History currently displays a timestamp, duration and persistent ID prefix,
plus an existing title if supplied in the session specification. The retained
v28 operator UI disabled Rename; this scenario does not claim a new rename API.
Individual deliberate deletion and selected export are supported. The earlier
host `test_storage.py`31-session test remains useful host evidence; it is not
substituted for this separately admitted native action.

## PowerShell host checks

```powershell
$env:LIVE_STORAGE_CHECK_ENTRY = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/storage-preparation/native-storage-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $env:LIVE_STORAGE_CHECK_ENTRY | Out-Null
$env:LIVE_STORAGE_ACTION_TEST_ROOT = Join-Path $env:LIVE_STORAGE_CHECK_ENTRY 'tests'
Set-Location 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_STORAGE_CHECK_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_native_storage_check')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun))); raise SystemExit(not r.wasSuccessful())"
```

## Command Prompt and Anaconda Prompt

```bat
set "LIVE_STORAGE_CHECK_ENTRY=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\native-storage-%RANDOM%-%RANDOM%"
mkdir "%LIVE_STORAGE_CHECK_ENTRY%"
set "LIVE_STORAGE_ACTION_TEST_ROOT=%LIVE_STORAGE_CHECK_ENTRY%\tests"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_STORAGE_CHECK_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_native_storage_check')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun))); raise SystemExit(not r.wasSuccessful())"
```

For authorized native dispatch, retain the early CPU14 owner wrapper from
`README_QUALIFICATION_DISPATCH.md` and use
`host_operations.py --label storage-check-launch-NN --action launch_storage_check_action.py --payload G:/PRIVATE/REVIEWED_STORAGE_PAYLOAD.json --writes`.
Use actual reviewed JSON paths and hashes. This dispatch is performed by the
native operator/root workflow, never by the synthetic unit tests.
