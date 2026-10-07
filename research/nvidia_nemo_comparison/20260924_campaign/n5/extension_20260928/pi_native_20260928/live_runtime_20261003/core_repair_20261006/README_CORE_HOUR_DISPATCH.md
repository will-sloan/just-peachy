# Frozen build30 continuous hour dispatch

Purpose: prepare and dispatch one sustained integrated headless application
session, continuously replaying the retained c24 processed PCM speech for
3,600 seconds through the ordinary Delayed/ReDimNet row. One source timeline,
worker and model session remain active across all 59 input wraps. This is
repeated recorded speech, not natural conversation, microphone capture,
spatial replay, GUI endurance or a quality evaluation. Successful source and
closure checks do not automatically qualify sustained realtime performance.

This document adds no runtime or helper edits. The frozen build29/build30
sources and existing sealed README remain unchanged. The commands below are
operator procedures, not evidence that an hour has run. Native actions and
SSH are dispatched only by the coordinating root operator after the existing
backup, ownership and lease gates pass. Wait for the actual Saved43–46 unit,
main-owner and nested-worker closure/finalization before another native job.

## Inputs and outputs

Inputs: actual immutable build30 PC package and manifest, accepted backup12
with its complete c24 source files, actual current native boot, reviewed
operator identity, fresh output/operation/unit labels, and the exact admitted
native c24 input path. The examples use the observed boot; recheck it at the
time of dispatch and regenerate preparation if it changed.

Outputs: a fresh registered host preparation containing source backups,
independent restores, the lossless joined WAV, SOURCE_JOIN/SOURCE_CLOSED,
STAGE_PAYLOAD.json and PAYLOAD.json; a separately backed exact-byte action
copy; guarded dispatch receipts and actual JOB metadata; a complete closed PC
mirror; and numeric REVIEW.json. Captions/audio remain private in the mirror.
The reviewer emits numeric counts, clocks and resource summaries, not words
or private speaker vectors. No native original source is overwritten/deleted.

The joined input is 1,932,844 bytes, 966,400 mono PCM16 samples at 16 kHz
(60.4 seconds). WAV SHA256:
`9a83534025736c2f057f20068f3c0584b45770815289a7842a501fcae52b65c8`;
PCM SHA256:
`0f13e54972e4140f5797b996bdeb48d802acd4dcbb9407065d46190bda887e97`.
Native input01 was never staged; build30 preparation uses fresh input02.
If input02 has already been successfully staged, verify its retained PASS
receipt and use it; do not rerun the fresh-directory stage action.

## Why the exact action copy is needed

`host_operations_v6.py:248–263`, reached through the V8 dispatcher, grants the
separate hour reservation only to action basename
`launch_full_app_soak_action.py`. It also requires the exact hour schema,
reviewed/workflow flags, repeat3600, runtime4680 and equal independent-copy
reservation. Passing `launch_core_full_app_hour30.py` directly retains the
ordinary 512 MiB ceiling and rejects the 2,306,682,336-byte hour reservation
before SSH. Do not raise that ceiling globally.

Copy the frozen `launch_core_full_app_hour30.py` bytes to a fresh private
`launch_full_app_soak_action.py`, with backup, independent restore and readback.
Its exact length is 9,192 bytes and SHA256 is:
`b31b3a0bbdbf8746c14fedb6d7934dd25941cce7b32862498f74329f92d0cec2`.
The action does not use its own `__file__` to locate dependencies. It fixes the
native build30 path/PIN, verifies the immutable package inventory, and reads
the shared envelope only from that inventoried package. Renaming the copy
preserves those checks. V8 independently backs/restores the dispatched action
bytes and records their SHA. No new Python adapter is needed.

## PowerShell: set paths and create the backed action copy

Run from an allocated host slot. The copy shell pins CPU14 and registers its
actual PID/creation FILETIME before project-source reads. All destinations use
CreateNew; existing files are never overwritten. The restore is reconstructed
from the backup, then independently hashed against the frozen source pin.

```powershell
$ErrorActionPreference='Stop'
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$D="$N/core_repair_20261006"
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$PACK="$Q/audit-preparation/sidecar-package30-99ab101518ce402a9a2c8d5f6ac96cc6/package"
$PIN='b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569'
$BOOT='e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
$REVIEWER='root: frozen build30 source review'
$INPUT='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/core-c24-endurance-input-02/c24-processed.wav'
$LABEL='full-app-hour-01' # Must be unused natively; otherwise prepare an unused NN.
$proc=[System.Diagnostics.Process]::GetCurrentProcess()
$proc.ProcessorAffinity=[intptr]16384
$copyRoot="$Q/audit-preparation/core-hour30-action-copy-$([guid]::NewGuid().ToString('N'))"
[IO.Directory]::CreateDirectory($copyRoot) | Out-Null
function WriteFreshBytes([string]$Path,[byte[]]$Bytes) {
    $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($Bytes,0,$Bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}
$ft=$proc.StartTime.ToUniversalTime().ToFileTimeUtc()
$owner=@{schema='just-peachy.host-registered-owner.v1';pid=$proc.Id;cpu=14;affinity_mask=16384;creation_filetime=$ft;create_time=($ft-116444736000000000)/10000000}
WriteFreshBytes "$copyRoot/REGISTERED_OWNER.json" ([Text.Encoding]::UTF8.GetBytes(($owner | ConvertTo-Json -Compress)))
$source="$D/launch_core_full_app_hour30.py"
$actionPin='b31b3a0bbdbf8746c14fedb6d7934dd25941cce7b32862498f74329f92d0cec2'
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $actionPin) { throw 'Frozen action hash changed' }
$bytes=[IO.File]::ReadAllBytes($source)
if ($bytes.Length -ne 9192) { throw 'Frozen action extent changed' }
$ACTION="$copyRoot/launch_full_app_soak_action.py"
WriteFreshBytes $ACTION $bytes
WriteFreshBytes "$ACTION.backup" ([IO.File]::ReadAllBytes($ACTION))
WriteFreshBytes "$ACTION.restore" ([IO.File]::ReadAllBytes("$ACTION.backup"))
foreach ($path in @($source,$ACTION,"$ACTION.backup","$ACTION.restore")) {
    if ((Get-Item -LiteralPath $path).Length -ne 9192 -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $actionPin) { throw 'Independent action readback failed' }
}
$copyReceipt=@{schema='just-peachy.core-hour-action-copy.v1';source=$source;action=$ACTION;bytes=9192;sha256=$actionPin;backup="$ACTION.backup";restore="$ACTION.restore";independent_readback=$true;source_unchanged=$true}
WriteFreshBytes "$copyRoot/COPY_READBACK.json" ([Text.Encoding]::UTF8.GetBytes(($copyReceipt | ConvertTo-Json -Compress)))
```

End this copy shell naturally after its work and independently check its
registered PID/creation identity absent before another dispatcher preread.
If preparation/dispatch uses another shell, set the same path variables and
set `$ACTION` to this actual fresh copied action, verified against its receipt.

## PowerShell: refresh preparation and stage input if needed

Each preparation uses a new output directory; preserve all expired/failed
preparations. The preparer writes both admissions with `time.time()+590`.
Refresh after input staging if either payload no longer has enough time for
the full guarded dispatcher preread. Do not edit an expired payload by hand.

```powershell
$PREP="$Q/audit-preparation/core-endurance30-refresh-$([guid]::NewGuid().ToString('N'))"
& $PY -B "$D/prepare_core_endurance30.py" --package $PACK --manifest-sha256 $PIN --backup-root "$Q/production-backup-12-reconcile-01" --census-sha256 c827fad465bb6a1307de9157d13b55d31115476f7354868963cbe5b19a2444ac --complete-sha256 03ffc85b2e2f3046c707879c3059f3c2e1194626f4ece11a7d385975c924bdfb --boot-id $BOOT --native-input-path $INPUT --operator-id delayed_redimnet --label $LABEL --reviewer $REVIEWER --output $PREP
if ($LASTEXITCODE -ne 0) { throw 'Preparation failed; retain its receipts' }
# Only when input02 has not already been successfully staged:
$stageOp='core-c24-input30-'+[guid]::NewGuid().ToString('N')
& $PY -B "$D/host_core_operations_v8.py" --label $stageOp --action "$D/stage_c24_endurance_input30.py" --payload "$PREP/STAGE_PAYLOAD.json" --writes
if ($LASTEXITCODE -ne 0) { throw 'Input staging failed; retain its receipts' }
```

Stage only through the root operator. Inspect the actual dispatch action PASS,
exact output/WAV/PCM hashes, unchanged original-source membership/hashes, and
independent utility closure before hour launch. Staging uses existing leases,
fresh native input02, 8 MiB output/PC reservation and the inherited 32 MiB
utility file limit. It launches no models. Re-run the preparation command with
a new `$PREP` after stage completion when necessary; skip the stage command
when the exact input02 PASS is already accepted.

## PowerShell: V8 hour launch, actual JOB, full mirror, review

After fresh current-boot ownership/lease admission and finalized Saved43–46,
dispatch the hash-verified copied basename. Existing native output and unit
names must be unused. The guard may reject changed ownership, RAM or capacity;
retain that result and resolve the actual blocker before a new operation.

```powershell
$launchOp='core-hour30-launch-'+[guid]::NewGuid().ToString('N')
& $PY -B "$D/host_core_operations_v8.py" --label $launchOp --action $ACTION --payload "$PREP/PAYLOAD.json" --writes
if ($LASTEXITCODE -ne 0) { throw 'Launch failed; retain its receipts' }
$dispatchPath="$Q/operation-$launchOp/dispatch/RESULT.json"
$dispatch=Get-Content -LiteralPath $dispatchPath -Raw | ConvertFrom-Json
$actualJob=$dispatch.action_result
if ($actualJob.schema -ne 'just-peachy.native-component-job.v1' -or $actualJob.unit -ne "jp-v29-$LABEL.service" -or $actualJob.package_manifest_sha256 -ne $PIN -or $actualJob.workflow -ne 'continuous-full-application-repeated-wav') { throw 'Actual returned job differs' }
$JOB="$Q/$LABEL-JOB.json"
# Preserve the actual returned fields; never invent PID/invocation/clock values.
$jobBytes=[Text.Encoding]::UTF8.GetBytes(($actualJob | ConvertTo-Json -Depth 50 -Compress))
$stream=[IO.File]::Open($JOB,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try { $stream.Write($jobBytes,0,$jobBytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
$MIRROR="$Q/$LABEL-monitor-$([guid]::NewGuid().ToString('N'))"
& $PY -B "$N/monitor_native_job.py" --job $JOB --output $MIRROR --poll-seconds 15 --copy-deadline-seconds 7200
if ($LASTEXITCODE -ne 0) { throw 'Full mirror incomplete; preserve partial evidence' }
# Only after actual FULL_CLOSED_OUTPUT_MIRRORED and MIRROR_COMPLETE:
& $PY -B "$D/review_core_full_app_hour30.py" --mirror $MIRROR --package $PACK --manifest-sha256 $PIN --output-root "$Q/audit-preparation"
if ($LASTEXITCODE -ne 0) { throw 'Read-only hour review failed; preserve evidence' }
```

The monitor performs read-only strict SSH; it never starts, renews, stops or
kills the service. It waits for same-boot exact main-owner absence and empty
original cgroup, then copies all regular output files through bounded segments.
Before/after source identities/membership, native segment hashes, independent
PC readbacks and full PC file hashes must match. `MIRROR_COMPLETE.json`,
`MIRROR_MANIFEST.json`, `EFFECTIVE_JOB.json` and `RESULT.json` preserve closure
and hash provenance. Complete mirroring and `functional_success=true` do not
substitute for the numeric hour review or model cleanup gates.

The reviewer verifies the full mirror and package, requires no nonempty SQLite
journal/WAL/SHM before immutable read-only open, runs bounded quick_check, and
checks 57,600,000 samples, 59 exact wraps, one model session, captions/PnC,
source append completion, final3600-second clocks, zero final lag/drops,
natural worker/job closure and capacity. It reports
`COMPLETE_3600_SOURCE_AND_CLOSURE` only when all gates pass, otherwise
`FAILED_OR_INCOMPLETE_PREFIX`. Resource trends and layer costs remain numeric,
descriptive evidence requiring interpretation; no acoustic-quality claim.

## Lifetimes and finite resource limits

The admission expires within 600 seconds and is checked at action/startup.
It is a start window: it does not terminate the service 600 seconds later.
The short host/native dispatch helper also has its own finite 600-second
scope; it exits after launching the independently owned service. Shared
SessionPolicy allows 3600s source +120s loading +600s drain +60s cleanup =4380s.
The explicit service adds300s reserve: RuntimeMaxSec4680, TimeoutStopSec30,
KillMode=control-group; its wrapper alarm is4670s. JOB deadline includes at
most15s additional registration slack, giving<=4725s. Monitor copy allowance
7200s extends only closure/transfer, never the native compute lifetime.

The hour reserves 2,306,682,336 native output bytes plus the same independent
PC copy, with an explicit3GiB/2048-file ceiling. Actual native physical free
space must retain the StoragePolicy reserve (at least5GiB); capacity-derived
per-file FSIZE is preserved. Host C:50GiB/G:75GiB floors apply; preparation and
monitor additionally reserve twice the complete job allocation plus8MiB.
V8 metadata utility usesCPU3/256MiB AS/1MiB stack with initial978MiB available
RAM floor, early owner and existing lease checks. Launched model/source limits
remain separate: CPU2,3/quota200%/Tasks64, worker768MiB AS, bounded queues,
192MiB available-RAM stop floor, 16MiB whole-unit trace/16KiB rows/atmost1Hz.
These explicit developer job/resource budgets do not restore logical user
recording/profile/gallery quotas. No optional parallel refiner is admitted.

## Command Prompt and Anaconda Prompt

Use the explicit qualified interpreter above; no environment installation or
activation is needed. In either prompt, enter:

```bat
powershell -NoProfile
```

Then run the same PowerShell blocks, in the order and allocated host/native
slots described above. Paths are absolute and work independently of the
current directory. Fresh directories/labels and actual current observations
are required; examples are not commands to replay a consumed admission.

Source-only documentation review: no new Python, native action, model,
recovery, activation or hour execution was performed to author this file.
