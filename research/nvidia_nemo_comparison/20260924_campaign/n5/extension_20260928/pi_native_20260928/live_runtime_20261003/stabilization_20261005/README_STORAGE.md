# Speech metadata and terminal cleanup storage

Purpose: provide capacity-governed recording/history storage with separate,
finite text, SQLite and terminal-fact allocations. This fresh runtime derivative
preserves the old recording store, failed recordings, existing ledger ceilings,
ownership leases and free-space floors. It is packaged into a new runtime; it
must not replace a deployed or historical storage.py in place.

The motivating native failure is session
`8c5d357f0acc4640bfcda4697d7e325b` on build24. Speech produced 19 nonempty
caption rows and 420 revision events over 808,000 processed samples (50.5s).
The ordinary SQLite meter rejected a 52,844-byte charge at 9,566,622 bytes
used against its 9,568,256-byte ordinary ceiling. The old cleanup event then
used the same exhausted meter. The recording remains failed; source and unit
OS closure are separate receipts and do not repair its logical cleanup result.

Inputs are a fresh session specification, the admitted StoragePolicy, and finite
audio/metadata writes. Outputs are disk-backed processed/raw segments, replay
WAVs, persistent paginated history/caption revisions, terminal facts and
independent readback/export manifests. No microphone/model/network/GUI is
started by this module. Existing deletion, keep/discard, replay and ownership
guards remain; only the explicitly selected recording can be deleted.

## Allocation and compatibility

The ordinary metadata reserve is split only when the fresh specification names
the split. An absent split retains the legacy one-sixth SQLite partition.
`text3_sqlite1_v1` retains its existing one-quarter SQLite partition.
`text1_sqlite1_v2` offers half text and half SQLite. Fresh worker specs select
`metadata_reserve_bytes=2*(16MiB + duration_seconds*256KiB)`, after the native
failed19 read-only producer census showed 15,646,953 work/text bytes in 50.5s.
Shrinking text to one-quarter of the old total would be unsafe. The new total
is an explicit allocation increase, charged in a fresh admission before use.
At70s the reserve is70,254,592B: text35,127,296B and SQLite36,175,872B including
the existing1MiB policy allowance; ordinary SQLite retains its256KiB closing
withhold. The separately admitted terminal pool is another256KiB. The full70s
processed plan is78,371,636B. Qualified packed4x16kHz PCM32 raw plus processed
and the existing32MiB helper margin is129,903,412B, requiring a fresh160MiB
reservation for each independent target and PC copy. An old128MiB admission
does not authorize the larger plan.

The observed text rate extrapolates to approximately21.69MB at70s. Its300s
extrapolation is approximately92.95MB against the new95.42MB text allocation;
this is modest headroom, not proof of all five-minute speech/diarizer workloads.
Bounded refusal/Stop remains required. No field duration or producer rate is
made unlimited, and no old or failed recording is granted more capacity.
The module does not select a new split for an existing session. Recorded meter
limits remain immutable, including failed or older sessions.

Fresh specifications can also reserve `terminal_metadata_reserve_bytes=262144`.
This 256KiB pool is additional to the ordinary reserve and policy allowance;
StoragePolicy.estimate_bytes includes it exactly once. Worker file/journal
allocation and each independent native/PC copy must include it before dispatch.
Zero or an absent terminal reserve preserves old specifications. Booleans,
other terminal sizes and unknown split names are rejected.

`SessionStore.write_terminal_event(session_id, kind, payload)` accepts one
immutable fact for each of `source_closure`, `session_cleanup`,
`saved_spatial_closed` and `session_failure`. Each JSON fact is at most 16KiB.
Four maximum charges total at most 135,168 bytes, inside the independent 256KiB
pool. Repeating an identical fact returns the original event; replacing it or
publishing another kind is rejected. Ordinary event/caption writers cannot spend
this pool. Terminal events remain available through the existing event reader,
but migration excludes them from ordinary allocation accounting.

Terminal facts describe observed cleanup attempts. They do not certify process
death. Caller source/model/lease checks and external exact owner/cgroup closure
remain required. A fault stays latched even when cleanup successfully releases
resources. Spool.fail records a bounded reason prefix and full reason hash,
then attempts both actual lease closes in finally. An unlock error closes its
file handle, the other lease is still attempted, and the error is retained.
Free-space checks still apply to terminal publication; resource release is
attempted even if that publication itself fails.

## Focused host check

`check_speech_storage_repair_v2.py` takes the new source directory, immutable
build24 package directory, numeric failed19 SQLite and work-byte inspection results and a fresh output
directory. It registers an actual CPU14 Windows owner before project reads,
backs up every input and independently restores it before importing code.
Its fixed scope is 60 seconds and 128MiB including retained synthetic stores;
C:50GiB/G:75GiB floors remain required. Never reuse an output directory.

The check compares all storage function/method ASTs, exercises a synthetic
70-second public source/caption writer volume against old and fresh policies,
plus the existing aggregate text writer at the observed70s extrapolated volume,
then separately tests ordinary exhaustion, terminal immutability, old-spec
rejection, terminal write failure and actual Windows lease-release failure.
Synthetic payloads contain no private recording audio, transcript or embeddings.
It does not establish native throughput, Linux closure, diarization accuracy,
or successful native speech recording. The actual numeric receipt is a basis
for the allocation repair, not a substitute for a fresh native session.

PowerShell, after setting these absolute paths:

```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$b="$q/audit-preparation/stabilization-package-cf9abd6dce8c4ccb99704310f74c90e5/package"
& $py -B "$s/check_speech_storage_repair_v2.py" --source $s --baseline $b --stats-file "$q/operation-speech-storage-inspect19-01/dispatch/RESULT.json" --work-stats-file "$q/operation-speech-work-inspect19-01/dispatch/RESULT.json" --output "$q/audit-preparation/speech-storage-repair-host-NEW-LABEL"
```

CMD or Anaconda Prompt (the same commands and existing environment):

```cmd
set "PY=C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe"
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
set "Q=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
"%PY%" -B "%S%/check_speech_storage_repair_v2.py" --source "%S%" --baseline "%Q%/audit-preparation/stabilization-package-cf9abd6dce8c4ccb99704310f74c90e5/package" --stats-file "%Q%/operation-speech-storage-inspect19-01/dispatch/RESULT.json" --work-stats-file "%Q%/operation-speech-work-inspect19-01/dispatch/RESULT.json" --output "%Q%/audit-preparation/speech-storage-repair-host-NEW-LABEL"
```

The output has REGISTERED_OWNER, HOST_SCOPE, exact SOURCE backups/restores,
V1 is retained as failed before public volume: the2TB Windows G: drive's default
5% storage floor exceeded its free bytes. V2 selects an explicit synthetic host
fixture policy with reserve_fraction=0; its5GiB StoragePolicy floor and the
stronger C:50GiB/G:75GiB check remain. Native StoragePolicy defaults are unchanged.
No failed or deployed recording is assigned this fixture policy.

The output has REGISTERED_OWNER, HOST_SCOPE, exact SOURCE backups/restores,
SOURCE_CLOSED, RESULT and EXIT_INTENT. EXIT_INTENT does not certify death;
an external read of the actual PID/create-time is needed for HOST_CHECK_CLOSED.
All fixture stores and faults are retained. Do not run this check while another
native dispatch prerequisite is collecting its owner snapshot.
