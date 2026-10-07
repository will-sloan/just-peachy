# Prepared qualification actions

The reviewed09 output guard records the exact failing path, mode, link count,
inode/device, file count and byte totals in its failure message. It accepts only
the two direct names `final` and `final.pending` on the same regular inode with
exactly two links, as created by `runtime_support.publish`. Both visible names
are counted and charged in full. A completed publication is accepted after a
same-inode re-stat shows one link; a stale listed member is skipped only after
its current path is confirmed absent. Other hard links, symlinks, changed
identities and file/byte cap breaches remain failures. CPU/time/disk limits do
not change. This repairs a plausible publication race without claiming that
the original08 generic failure established its exact path or link count.

Host-only focused checks extract just the pure output guard from the generated
wrapper; they never execute its native bootstrap. Run through the existing
CPU14 early-owner test procedure below, selecting
`test_output_guard_exact_pending_pair_and_external_alias_refusal`,
`test_output_guard_publication_unlink_races_are_rechecked`, and
`test_output_guard_count_has_exact_failure_details`. Inputs are fresh tiny host
fixtures; outputs are the existing test result/source receipts. Native
PowerShell/CMD/Anaconda dispatch commands remain unchanged.

`launch_raw_qualification_action.py` is an injected action for
`host_operations.py`. It prepares one fresh five-second source-only raw test.
It does not run when imported for host tests. Dispatch uses the existing user
authorization plus fresh admission, complete host/native ownership inspection, a current
boot and expiry, the exact immutable package inventory, and a reviewed template.
No GUI or speech model is part of raw qualification.

The default requested trial is `raw-qualification-01`, below the native campaign
directory `live-runtime-tests-20261003`. Labels and output roots are single-use.
The service is `jp-v29-<label>.service`, CPU2/3, aggregate 200%, Tasks64,
768 MiB address space, 1 MiB stack, 32 MiB per-file limit, lifetime 180 seconds
and stop grace 30 seconds. A finite supervisor alarm and independent output
guard remain armed. Only the RESEARCH exclusion lease is held by the wrapper;
the actual isolated source acquires its own hardware lock.

The wrapper publishes its actual PID/start-ticks/boot `OWNER.json` before any
project read. It re-verifies the complete package with the pinned pure scope
helper, then checks MainPID, InvocationID, control group membership and actual
systemd limits. It writes `UNIT_OWNERSHIP.json`, creates the fresh unit-bound
`RAW_ADMISSION.json`, and calls the pinned `raw_qualification.py` through runpy
in that same process. The harness creates the new `qualification` subdirectory
and owns its experimental recording store. Existing recordings are not used.

Inputs are a private JSON payload containing:

- `package`, `package_manifest_sha256`, actual `boot_id`, and `expires_unix`
  within the fresh 600-second scope.
- `label: raw-qualification-01` and `maximum_output_bytes: 16777216`.
- `raw_admission_template` as an object with the schema and exact fields
  documented in `README_RAW_CAPTURE.md`.
- `raw_admission_template_sha256`: SHA256 of that object's UTF-8 JSON encoded
  with sorted keys, separators `(',', ':')`, and nonfinite numbers forbidden.

The template's expiry must not exceed the action expiry. It binds the five-second
duration, target, package manifest, binding, installed-source/raw-capture hashes
and current boot. Unit/InvocationID are filled only after observing the actual
service, never guessed in a template.

Native output reserves 16 MiB above the existing 5 GiB disk floor. The host
independently reserves a complete 16 MiB copy above C:50 GiB and G:75 GiB floors.
The output guard rejects more than 256 files and preserves 256 KiB for terminal
receipts. Python stdout/stderr have separate 64 KiB caps; native stdout/stderr
share a 256 KiB bounded capture pipe. Exceeding a cap fails the job with its
accepted prefix retained. The guard detects aggregate growth; RLIMIT_FSIZE is
a per-file limit and is not a filesystem quota. Final mirroring requires the
entire closed tree to fit its declared reservation.

Outputs include exact payload/budget/wrapper provenance, owner/unit/admission
receipts, bounded logs, the harness's experimental audio and physical-close
evidence, durable `JOB_EXIT.json`, and `JOB.json` with the unchanged
`just-peachy.native-component-job.v1` schema. Launching is not qualification
success. The independent monitor must prove owner/cgroup closure and copy/hash
every output file; the raw harness must separately pass all physical checks.

## Prepared headless companion

`launch_pipeline_qualification_action.py` uses the same verified wrapper builder
from a package that includes `launch_raw_qualification_action.py`. It accepts
`label: pipeline-qualification-01`, exact RuntimeSelection/SessionPolicy objects
under `selection` and `policy`, plus a pinned `input`/`input_sha256` for saved WAV
input. It invokes the unified launcher with `--headless --keep-processed`.
Native authorization remains the launcher's and worker's responsibility.

Its independently pinned `maximum_output_bytes` must equal
`budget_plan(package, binding, payload, 'pipeline')['maximum_output_bytes']`:
the full StoragePolicy estimate plus another metadata/journal allocation,
8 MiB journal overhead and 2 MiB wrapper/log allowance. The wrapper's finite
per-file ceiling is the full pinned output reservation; the worker narrows it
after Manager has initialized the real SQLite history database. This includes
the nonzero initial database pages that the first failed saved qualification
revealed. The global output bound and independent PC/native reservations remain
unchanged; raw's32 MiB ceiling is not reused for the pipeline.
Long developer soaks are excluded. Budgets above the reviewed monitor's 256 MiB
limit need a separately reviewed monitor extension before dispatch. This
companion is prepared for later qualification, not implicitly admitted now.

## PowerShell, Command Prompt and Anaconda

For **authorized dispatch only**, use the qualified Python with an early CPU14
owner wrapper before `host_operations.py` is read. Set a fresh private entry
directory and real reviewed payload; these examples do not create admission:

```powershell
$n = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$env:LIVE_QUALIFICATION_ENTRY = 'G:/PRIVATE/FRESH_QUALIFICATION_ENTRY'
New-Item -ItemType Directory -Path $env:LIVE_QUALIFICATION_ENTRY | Out-Null
Set-Location $n
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json,sys; from pathlib import Path; p=Path(os.environ['LIVE_QUALIFICATION_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import runpy; sys.argv=['host_operations.py','--label','raw-qualification-launch-01','--action','launch_raw_qualification_action.py','--payload','G:/PRIVATE/REVIEWED_RAW_PAYLOAD.json','--writes']; runpy.run_path('host_operations.py',run_name='__main__')"
```

From **CMD or Anaconda Prompt**, set `LIVE_QUALIFICATION_ENTRY`, create that
fresh directory, and use the same `-B -c` string with double-quoted executable:

```bat
set "LIVE_QUALIFICATION_ENTRY=G:\PRIVATE\FRESH_QUALIFICATION_ENTRY"
mkdir "%LIVE_QUALIFICATION_ENTRY%"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
```

The explicit environment path avoids the Windows Store alias. Do not run the
action file directly on the PC; it is injected only by the reviewed dispatcher.

For **hardware-free tests**, use that same early registration prefix, set
`LIVE_QUALIFICATION_TEST_ROOT` to a private temporary-test directory, and replace
the runpy suffix with:

```python
import unittest
r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_qualification_dispatch'))
(p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,native_executed=False,ssh_executed=False)))
raise SystemExit(not r.wasSuccessful())
```

Tests exercise full inventory tamper/traversal refusal, exact fresh template
pins and expiry, and compile the finite wrapper without executing it. All
fixtures are synthetic and have no native qualification authority.
# Raw helper qualification pin

Fresh raw admission templates also require `source_batch_sha256`, the exact
SHA256 of packaged `source_batch.py`, alongside the installed-source and
raw-capture hashes. Both the action wrapper and source-only harness verify it.
This prevents reuse of frozen build04 qualification for the changed optional
batch helper. Existing immutable evidence remains unchanged.

For the full GUI workflow, the reviewed payload may specify `stop_mode:"policy"`,
`stop_after_seconds:300` and `save_raw:true`. Policy Stop is restricted to the full
live300s capture; it injects no Stop-button action. Raw saving requires the actual
raw-enabled binding and proof. `stop_mode:"button"` permits an explicit1..300s
boundary. Both modes preserve the complete two300s-session allocation and1500s
service lifetime. The dispatcher forwards `--stop-mode` and optional `--save-raw`
to the pinned driver; its complete replay and sample-count checks are documented
in `README_NATIVE_GUI_DRIVER.md`. Existing absent fields mean button Stop and
processed saving, preserving the earlier short GUI protocol.

