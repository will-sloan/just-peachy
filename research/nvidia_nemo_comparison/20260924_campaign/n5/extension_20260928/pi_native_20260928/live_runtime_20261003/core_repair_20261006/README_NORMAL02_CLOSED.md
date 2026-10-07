# Closed normal02 diagnostic

Purpose: inspect the exact closed normal production session after the external
RUNNING predicate timed out. This is source preparation and read-only diagnosis;
it does not Start, Stop, replay, recover, delete, acquire a lease or load a model.
It is not a successful ordinary GUI test. Frozen build35 runtime remains intact.

Inputs are the fixed build35 manifest, current boot, launch
`1c846cf0acba464485dc5222a6158529`, session
`2013dbd12ca74e979d9b809c41e3a90f`, app145677/start3512160 and
worker145686/start3512244. The native action accepts only a matching payload
which expires in ten minutes and a guarded BASELINE showing closed ownership.
It rejects a live matching app, worker or registered source.
Source registration uses the exact six-field installed source-owner envelope
with nested three-field owner identity; it is not the worker-owner schema.

Outputs are `ACTION.py`, `PAYLOAD.json`, exact source backup/restore files and
`SOURCE_CLOSED.json` in a new private host directory. Native dispatch returns
selected numeric SQLite counters, sanitized named worker/source failure
metadata, hash/count-only bounded worker-log diagnostics, current RAM/disk,
systemd state and recorded lease-owner status. Lock-file existence is explicitly
not evidence of lock ownership. No audio, transcript, caption text, people or
embedding vectors are returned. Missing receipts are reported as missing.

The action lowers inherited hard limits to at most128MiB address space,1MiB
stack and zero file/core writes, uses CPU3 and a20-second alarm. It emits an
exact process-owner registration to stderr before reading project data. The
reviewed dispatcher retains its independent native owner/closure evidence.
Failure under these bounds is retained; no limits are raised for diagnosis.
SQL is mode=ro/query_only with256KiB cache and a3-second progress deadline.
Selected metadata is at most256KiB per file, the worker log at most512KiB,
and the resulting numeric document at most64KiB.

PowerShell source preparation (no native execution):

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime_20261003'
$out="$q/audit-preparation/normal02-closed-REPLACE_WITH_FRESH_LABEL"
& "$d/prepare_normal02_closed.ps1" -OutputDirectory $out
```

Root reviews the preserved sources, exact pins and fresh payload before the
existing V15 guarded dispatch. This command is an operator procedure, not a
claim that it has run:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$d/host_core_operations_v15.py" --stage35-admission "$d/CORE_STAGE35_ROOT_ADMISSION.json" --stage35-admission-sha256 '345d527c78033ea54946e5c8104420f3009515c34a8a179876e5cca8f9e11d70' --label core-normal02-closed-inspect-01 --action "$out/ACTION.py" --payload "$out/PAYLOAD.json"
```

Command Prompt and Anaconda Prompt: run `pwsh -NoProfile`, then the same blocks.
Use the existing interpreter without installing dependencies. Do not reuse an
existing output directory or expired payload. Preserve natural exit and exact
host/native OS-closure receipts, all raw failures and independent output hashes.

Static finding: sealed35 `SessionSpool._append` commits
`sessions.processed_samples` on every processed append. The counter is not
Stop-only. The controller also requires a mapped label starting `Listening`;
the closed-worker evidence must distinguish absent capture, a stalled health
channel and an observer mismatch. Live53 used delayed/TitaNet, while this
ordinary check selected Pyannote/ReDimNet, so their Start results are separate.
No inspection result or runtime repair is claimed before root executes it.
The first host-only prepared copy was held by root review before native use
because it expected an unnested source owner. Its exact source triples remain
in the private preparation directory. The current action corrects only that
registration check; the actual `segments.kind` query matches sealed storage.
