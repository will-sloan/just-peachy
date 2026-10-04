# Guarded production activation and actual idle/Exit check

Current injected consolidation uses [README_DESKTOP_CONSOLIDATION_V3.md](README_DESKTOP_CONSOLIDATION_V3.md) and `desktop_consolidation_action_v3.py`, preserving exact manifest-pinned imports, the original transaction and all11 shortcut/startup pins while adding complete bounded PC archive readback. Use the current reviewed V6 dispatcher.

The current planned sequence is production16 activation, V3 consolidation, then
[V2 idle/policy inspection](README_PRODUCTION_IDLE_V2.md). Production16 remains
pending until actual receipts are reviewed. Original idle files are preserved
history; current commands use launch_production_idle_action_v2.py.

These external utilities fill the final activation/idle-check steps. They do not
change any frozen package, installer, native scope, model, v27/v28 source or
recording. Only the root operator executes native actions, after existing user
authorization, fresh admission, all prior exact owners/units closed, and verified
production acceptance. Preparation and host tests execute no Pi command.

## Activation inputs and behavior

`desktop_activation_action.py` is injected by the existing `host_operations_v6.py`
inspector. It requires the current inspector's real PID/start ticks/boot ID to
match the in-memory baseline, all runtime owners closed, both exclusion leases,
the existing 5 GiB native disk floor plus 16 MiB metadata reserve, and the existing
32 MiB inspector file limit. It does not raise limits or create another process.

The action verifies the entire exact production package, acceptance, full-backup
manifest/completion and selected old desktop hash. It imports `profiles`,
`optional_refiner_admission`, `release_authorization` and
`optional_refiner_dispatch` only from their pinned canonical package paths and
refuses an already loaded module from another origin. This lets the unchanged
`install_candidate.activate` resolve its validation dependencies correctly.
Optional eligibility remains subject to the actual accepted evidence and any
reviewed relocation certificate; this action cannot turn preparation into proof.

Before replacing the selected shortcut, the action fsyncs the complete fresh
baseline and a separate byte-identical restore copy, actual inspector reference,
import pins and activation intent into a fresh evidence directory. The unchanged
installer independently saves both old-desktop copies and its activation plan,
then atomically replaces only that selected shortcut. The action checks all
copies/current bytes and returns the small artifacts with hashes and base64.
The larger baseline is losslessly reconstructed from the exact listed baseline
fields already present in the closed outer inspector RESULT; it is not duplicated
into the bounded stdout envelope. This is a real reference to the inspector,
not a fabricated second owner identity.

Activation payload, with real reviewed values replacing placeholders:

```json
{
  "boot_id": "<current native boot UUID>",
  "expires_unix": 0,
  "package": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-16",
  "package_manifest_sha256": "<production package manifest SHA256>",
  "production_acceptance_sha256": "<exact acceptance SHA256>",
  "backup_manifest_sha256": "<accepted full-backup manifest SHA256>",
  "backup_completion_sha256": "<accepted full-backup completion SHA256>",
  "desktop": "/home/peachyprototype/Desktop/<selected existing owned shortcut>.desktop",
  "previous_desktop_sha256": "<accepted exact old desktop SHA256>",
  "evidence_root": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-activation-<fresh32hexUUID>",
  "maximum_output_bytes": 16777216
}
```

Expiry must be a real current-boot numeric deadline no more than 600 seconds in
the future. `build-16` is planned only and illustrative; use the actual production package, never
a disabled or qualification package. The accepted full backup must already
contain the selected original desktop. The action makes no startup/autostart,
capture or other-shortcut change. Desktop consolidation remains a separate exact
11-file transaction described in README_DESKTOP_CONSOLIDATION.md.

Activation outputs: the fresh native evidence directory, installer-generated
`field-runtime-v29-desktop-backup-<UUID>` with `.backup`, `.restore` and
`ACTIVATION_PLAN.json`, current desktop hash, guarded operation/closure receipts,
and a complete host reconstruction/readback. The host-only CLI refuses a changed
action source, mismatched natural inspector closure, missing artifact membership,
changed baseline fields or bad bytes/hashes. It preserves two independent copies
of the closed RESULT and all ten native metadata files under its private output.
Failure keeps previous evidence and requires explicit review; no automatic
rollback or cleanup erases the audit trail.

## Actual desktop Exec idle/Exit check

`launch_production_idle_action_v2.py` embeds the exact adjacent
`production_idle_control_v2.py`. It checks the activated desktop hash and parses its
exact Exec line, including the production `native_scope.py`, binding, manifest
and default `/home/peachyprototype/JustPeachy/data/runtime-v29` argument. That data
root must be absent or empty immediately before launch; an existing nonempty
root is preserved and refused. There is no silent substitution of another path.

The controller launches that exact command as a directly owned child. It waits
for the actual outside owner, nested service owner, native scope ownership ACK,
systemd InvocationID/cgroup and actual 7,200-second production service envelope.
It selects the Tk interpreter by the remote Tcl builtin `pid`, matches that PID
to the registered GUI MainPID and current boot/start ticks/cgroup, and repeats
the identity check before every control request. It never assumes an interpreter
name such as `tk`. The retained Tcl-send examples used for this method are
`final-delivery-normal-stop-v1/source-backup/inspect_native.py` and
`final-delivery-idle-start-v2/source-backup/inspect_native.py` in the private
campaign evidence.

The test disables the real Start button, records ten stable fullscreen
480x800+0+0 observations, selects experimental Pyannote/TitaNet/live/window60,
checks the enabled optional control and exact300/load120/drain60/backlog30/
cleanup60 summary, then unchecks it and verifies unchanged ordinary defaults.
Start remains disabled around every policy command. It remains idle for five seconds, then invokes the actual
Exit-to-desktop button. No Start command or model constructor is called. It
requires zero worker launch records, natural outside-process reap, successful
SERVICE_EXIT/UNIT_CLOSURE, exact nested GUI-owner disappearance and empty nested
cgroup. The unchanged desktop source must remain available for later normal use.

A separate immediately started systemd watchdog publishes its actual owner
before reading inputs. Its deadline is 90 seconds and it can terminate only the
authenticated nested unit after rechecking InvocationID/cgroup. The production
service's 7,200-second property remains unchanged. The outer test and watchdog
each have a 120-second service limit, allowing bounded closure after the
90-second test deadline; this is not reported as a 90-second production service.
The controller waits for watchdog closure as well. A missing ownership ACK cannot
be converted into a guessed PID kill or a successful result. Ordinary outer
cgroup closure alone is insufficient to pass this nested test.

The complete new, closed default-data metadata is independently read back under
`production-data-readback`, bounded to 128 traversal entries / 4 MiB, with no
audio or media copied. Original default-data metadata plus this copy and test
receipts fit the separately reserved 16 MiB. The normal monitor must obtain the
complete closed outer mirror; review `PRODUCTION_IDLE_RESULT.json`, actual
nested UNIT_CLOSURE, watchdog exit and the independent readback inventory.
This proves programmatic actual desktop-command execution and normal Exit when
it passes. It does not claim a desktop double-click, reboot, physical touch,
caption quality or another capture qualification.

Idle payload uses the same current production package/acceptance pins, current
boot and fresh expiry, plus:

```json
{
  "label": "production-idle-01",
  "desktop": "/home/peachyprototype/Desktop/<activated selected shortcut>.desktop",
  "desktop_sha256": "<actual activation current_sha256>",
  "maximum_output_bytes": 16777216,
  "verify_optional_policy": true
}
```

## PowerShell

Prepare the two reviewed JSON payload files using actual returned values. No
activation command is authorized by placeholders. The existing host dispatcher
publishes its CPU14 owner before project/data reads and reserves C:50 GiB/G:75 GiB
plus the independent 16 MiB output allowance before SSH.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$n/host_operations_v6.py" --label desktop-activation-01 --action "$n/desktop_activation_action.py" --payload "$q/REVIEWED_ACTIVATION.json" --writes
# Host-only complete artifact reconstruction after the actual natural closure:
& $py -B "$n/desktop_activation_action.py" --operation "$q/operation-desktop-activation-01" --output "$q/desktop-activation-01-readback-01"
# Next complete the reviewed shortcut consolidation and its independent readback.
# Run idle last, after those successful readbacks, with a fresh idle payload:
& $py -B "$n/host_operations_v6.py" --label production-idle-01 --action "$n/launch_production_idle_action_v2.py" --payload "$q/REVIEWED_IDLE_V2.json" --writes
# Save the returned actual action_result as production-idle-01-JOB.json.
# Then use the exact reviewed monitor command from README_JOB_MONITOR.md,
# targeting that JOB and a fresh production-idle-01-monitor-01 directory.
```

## Command Prompt or Anaconda Prompt

Enter `powershell -NoProfile`, then use the complete PowerShell block. The exact
qualified interpreter requires no environment activation or installation.

For the host-only focused checks, use a fresh early-owner wrapper:

```powershell
$env:ACTIVATION_SOURCE=$n
$env:ACTIVATION_TEST_RUN=Join-Path $q ('storage-preparation/activation-test-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $env:ACTIVATION_TEST_RUN | Out-Null
& $py -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['ACTIVATION_TEST_RUN']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=[14]),f); f.flush(); os.fsync(f.fileno()); f.close(); import sys,tempfile,unittest; (p/'tests').mkdir(); tempfile.tempdir=str(p/'tests'); sys.path.insert(0,os.environ['ACTIVATION_SOURCE']); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_guarded_activation')); raise SystemExit(not r.wasSuccessful())"
```

Tests exercise the unchanged installer on synthetic files with only host platform
adapters, exact import origins, acceptance/backup refusal before mutation, full
baseline/artifact recovery, unchanged actual frozen wrapper composition, nested
7,200-second ownership, and watchdog refusal of a changed invocation. They do
not execute Tcl, native_scope, systemd, SSH, a model, or a capture on the PC.

The idle action preserves the complete fresh outer `BASELINE.json`. Its request
pins the six existing files from that inspection: `install/current.json`,
`data/live_config.json`, `data/settings.json`, `.config/kanshi/config`,
`.config/autostart/just-peachy.desktop`, and `start-prototype.sh`, plus the exact
selected desktop. `STATE_BEFORE.json` and `STATE_AFTER.json` independently check
their sizes/hashes, explicit disabled autostart flags, the already observed
closed `/proc/asound/.../status` paths, and the unchanged `wlr-randr` stdout hash
with `Transform: 270`. These are read-only checks; no display rotation or audio
control command is issued. The result includes the current desktop hash after
normal Exit and the baseline file hash. Missing baseline members are refused.

Tcl may destroy its remote interpreter before returning the real Exit button's
reply. That reply error is retained separately from the single invocation attempt.
Success still requires natural zero exit from actual `native_scope`, its normal
service exit and exact nested unit/process closure; attempting Exit is insufficient.
The watchdog's owner, ownership, exit and final cgroup closure receipts are kept
separately from the ordinary outer job closure. Copying the closed default data
metadata preserves the nested outside/main owners and native scope closure.
