# Closed Saved27 failure inspection

Purpose: diagnose only failed Saved27 launch8d61371110d0470c93f4ff58cc73027d
without clearing its recovery fence or modifying any recording. It binds exact
build25, current boot, actual JOB27 digest, original request and kept-source SHA.
The main owner/cgroup and recorded worker must be exactly absent first.

Inputs: a fresh payload with package_manifest_sha256, boot_id, launch_id and
expires_unix; full V5 current-owner preread; exact closed launch files. The action
reads at most32MiB per file,512files/768entries and256MiB per relevant tree,
hashing stable identities/membership before and after. The original source JSON
is rechecked without replay. Only the pinned native_scope helper executes.

Outputs: hashes/extents, actual owner absence, selected source/profile/mode,
worker RESULT/EXIT/cleanup/source/spatial scalar facts, source-owner receipt
presence, fence state and error classes. No captions, names, vectors, log tails,
model execution, microphone or current IMU are returned or started. The action
does not certify its own death; independent wrapper closure remains required.

Host preparation sets CPU14 and registers actual kernel-FILETIME identity before
project reads. Back up action/README and independently restore/read them before
compile and payload generation; use a fresh private directory and590s lifetime.
No unchanged healthy suite is needed for this diagnostic.

PowerShell preparation:

```powershell
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$s/prepare_saved27_failure_inspection.py"
```

CMD or Anaconda Prompt preparation, after setting S as below:

```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/prepare_saved27_failure_inspection.py"
```

The preparer outputs a fresh private ACTION/PAYLOAD directory, exact source
backups and independent restore copies, a30s/2MiB scope and actual CPU14 owner.
It verifies the actual JOB27 digest before emitting the finite payload.

PowerShell dispatch (after exact preparation host-owner closure):

```powershell
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$s/host_stabilization_operations_v5.py" --label saved27-failure-inspect-01 --action 'FRESH_PREPARATION/ACTION.py' --payload 'FRESH_PREPARATION/PAYLOAD.json'
```

CMD or Anaconda Prompt:

```cmd
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/host_stabilization_operations_v5.py" --label saved27-failure-inspect-01 --action "FRESH_PREPARATION/ACTION.py" --payload "FRESH_PREPARATION/PAYLOAD.json"
```

Do not add --writes, reuse a consumed label, remove pending files or synthesize
a physical microphone identity for a saved source. Status remains prepared until
actual read-only execution and independent closure are observed.
