# Physical output enforcement for the prepared live entry

Purpose: intercept Python file opens, writes, directory creation, publication and
deletion in the actual prepared live parent and source child. The existing producer
writers keep their tighter limits. This layer rejects unassigned physical paths,
second session/conversation/epoch/runtime tokens, file/aggregate excess, retained
file truncation, and unassigned links/deletion before those operations.

`field_live_files_v1.py` uses the V108 physical projection and the admitted flat code
manifest. It installs wrappers for builtins/io open and os descriptor/mutation APIs,
plus an audit hook that rejects cached writable opens and filesystem mutations
bypassing those wrappers. Appends use the actual end even after a seek; memoryview
writes count bytes rather than elements. Ordinary writes flush through the Python
buffer before returning. Failures retain partial files, latch the failed path and
signal attached nonblocking Stop callbacks before caller diagnostics.

This is Python producer enforcement, **not a kernel filesystem quota or protection
against arbitrary native-library writes**. It has not run on the Pi or with the live
controller/source/model. Existing sampled/outer storage guards and native source
review remain required. Hardware lease contents are preserved: only its exact
existing one-byte inode may be opened, and content writes are forbidden. Current
read-only Pi preflight measured that one-byte lease. The installed DeviceLease
does not rewrite a nonempty lease. Runtime-lock temporary/publication links and
owned cleanup are the only permitted unlink/link operations.

## Production wiring

Fresh derivatives select:

`field_live_controller_v3` → `isolated_pipeline_source_v6` →
`isolated_live_facade_v4` → `isolated_live_transport_v2` →
`field_live_source_factory_v2` → `field_live_source_bridge_v2`.

`field_live_source_outputs_v2.load` first validates the genuine admission and pinned
files using the retained source checks, then attaches the physical guard. It does
this in each actual process before owner/source receipts and construction. Up to
eight matching attachments share one guard; later loads cannot change the root or
code manifest. Callbacks look up the current real Stop function. Controller V3
connects its first outputs object to ControllerRef, and returns `physical_files`
alongside the D1 binding context. All old sources remain immutable.

Inputs: the same CONFIG/ADMISSION and explicit D1 binding documented in
README_FIELD_LIVE_D1_V1.md, with these fresh source names and all helper hashes.
Outputs: existing fixed file slots and bounded in-memory guard state. The future
entry must retain `physical_files.census()` after physical closure, including actual
IDs, member sizes, directories, failures and zero writable descriptors. Unknown
files never become declared merely because a census discovers them. Admission,
worker/process ownership, CPU/RAM/deadline/outer guards and closed-tree SSH backup
are still the entry's responsibility. No standalone microphone CLI is provided.

## Host verification CLI

`verify_field_live_files_v1.py` sets CPU14 before project reads. Inputs are a fresh
host-only preparation admission and a unique absent output directory inside its
allocation. The output contains small byte fixtures and receipts/RESULT.json with
cases, actual sizes and descriptor closure. It performs no installed imports,
models, audio, GUI or Pi actions. Do not rerun a passed output for a new version.

PowerShell:

```powershell
$native = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$native\verify_field_live_files_v1.py" --admission 'ABSOLUTE_FRESH_ADMISSION.json' --output 'ABSOLUTE_NEW_PRIVATE_DIRECTORY'
```

Command Prompt or Anaconda Prompt:

```bat
set "JP_NATIVE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%JP_NATIVE%\verify_field_live_files_v1.py" --admission "ABSOLUTE_FRESH_ADMISSION.json" --output "ABSOLUTE_NEW_PRIVATE_DIRECTORY"
```

Use the existing environment without downloads. Replace both uppercase paths with
the actual newly admitted inputs. The live entry uses installed rc5 Python with
`-B`, genuine source authority and fresh native admission; invoking this host CLI
does not grant any of those capabilities.

Current evidence: one host run,12 cases including10 changed rejects,53,754 fixture
and receipt bytes; runtime link/cleanup and pending publication succeeded. Overflow,
append offset, memoryview bytes, unknown paths/directories, code overwrite, second
conversation/session, retained deletion and cached-open bypass rejected. These
checks do not establish native integration, concurrency, physical exhaustion,
power-loss recovery, or acceptance of any live mode.
