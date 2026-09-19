# Serial paced dispatcher V3

Purpose: serialize a finite, separately authorized queue of the exact existing paced runners while recording dispatcher progress as bounded immutable heartbeat snapshots. This repairs the recurring mutable HEARTBEAT.json replacement failure. V1, V2, their outputs, and the native runners remain untouched. No runtime is launched by this source preparation or test. A past failed dispatcher can leave its original coordinator running; only root resolves that closure and defines a fresh remaining queue.

## Narrow change

Every existing 15-second dispatcher observation is serialized to heartbeats/BBB/HEARTBEAT_NNNNN.json within the fresh dispatcher output root. Sequence starts at 1, increases once per observation across batches, and never reuses a filename. Blocks hold at most 1,000 sequence numbers; at most 20 blocks and 20,000 observations are permitted. Each JSON is at most 16,384 bytes: the absolute payload bound is 327,680,000 bytes (312.5 MiB), plus filesystem metadata. At 15-second spacing the count covers more than 83 hours, beyond the unchanged stage time window. Limits fail closed.

Snapshots use exclusive creation, write, flush and fsync. There is no mutable latest pointer, temporary-file replacement, deletion, rename, heartbeat retry, or update of an earlier snapshot. A reader may hold an old snapshot open indefinitely without blocking creation of the next one. Any creation/write/flush/fsync error, collision, invalid sequence or size violation is propagated through the original dispatcher failure path. Partial files remain preserved. This avoids the observed replacement operation; it does not suppress other storage errors or identify the cause of the earlier access denial.

The old V2 save/replace_heartbeat functions remain exact for source continuity; the runtime heartbeat path no longer calls them. Existing immutable ADMISSION, LAUNCH, RESULT and transition writes are unchanged. The only existing run changes are the local sequence initialization/increment, heartbeat call, and V3 README binding. Queue selection, grids, helpers, source pins, PID/creation identity, quiet lease, per-cell completion, deadlines, stops, native parameters and failure/finally handling are exact V2.

## Inputs and output authority

The existing CLI accepts two explicit absolute JSON path/SHA256 pairs: --queue PATH SHA256 and --authority PATH SHA256. Queue schema remains s6c-serial-paced-queue.v1 with status REGISTERED_FINITE_QUEUE and 1–64 unique item/manifest/output-root rows. Every item retains its exact held helper binding, original manifest binding, requested cells and output root.

Root authority retains schema s6c-serial-paced-authority.v1, status AUTHORIZED_SERIAL_QUIET_PACED, exact queue binding, exact new V3 dispatcher binding, both quiet assertions true and an aware expires_utc no later than 2026-09-13T11:35:40Z. Existing queues/authorities must not be silently relabeled. Root must explicitly construct a fresh remaining queue/namespace excluding already started or completed batches. A prepared original manifest is allowed; any existing original invocation directory is refused.

Output remains REPORT/serial_paced_dispatcher/NAMESPACE, newly created exclusively. It contains original immutable ADMISSION.json, RESULT.json and per-item launch/quiet/transition records, plus the new heartbeats block directories. There is no V3 HEARTBEAT.json. A snapshot is an observed state, never owner closure, native completion, scientific acceptance or final stage acceptance.

Original runtime command remains EDGE -B HELPER run --manifest MANIFEST --quiet-admission NEW_QUIET.json. Only the held canonical/sentinel/cross fast_v2 and historical B00/B01/B36 fast_v1 paced helpers are allowed. No continuous helper, process termination, lease removal, automatic batch retry, takeover, skip or resume is introduced. Original complete grid and exact closed-owner/archived-lease evidence is still required before advancing.

## Efficient latest observation

An hourly reader lists at most 20 numeric block directories, starting with the lexically highest, then at most 1,000 numbered filenames in that block in descending order. Read only the highest successfully parsed snapshot. An empty newest block or currently in-progress file can be skipped in favor of the previous valid observation. Files are immutable only after successful close; live readers must tolerate a briefly incomplete new file and label the observation by its own created_utc. No full runtime tree scan or reading all snapshot bodies is required. Missing or stale telemetry is not a closure conclusion. The original RESULT and runner closure chain remain authoritative.

## Tests

test_s6c_paced_dispatch_v3.py shares this README. Inputs are preserved V2, current V3, this README and a fresh test output directory. Output is a source-bound SOURCE_CHECKS.json. Tests reverse exactly the allowed run delta and compare every inherited function and remaining module statement. They cover repeated injected Windows replacement denial, actual repeated WinError5/32/33 under a private Windows read handle, successful new snapshots while the prior one stays locked, exact bytes, block/sequence/size bounds, collisions, and propagated creation/fsync errors. No subprocess/model, actual queue, live lease, runtime source, audio, asset or inventory is accessed. The real Windows fixture is required.

## PowerShell

Use the existing exact interpreter; no installation or activation is needed. Choose a fresh checks output path. The run line is only a template and requires root's exact new authority after verified closure.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$edgePy = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edgePy -B test_s6c_paced_dispatch_v3.py --output '..\reports\S6C\20260910T123540Z\serial_paced_dispatcher\source_checks_v3_NEW'
# Only after root supplies the exact reviewed queue and authority:
& $edgePy -B s6c_paced_dispatch_v3.py run --queue 'ABSOLUTE_QUEUE.json' EXACT_QUEUE_SHA --authority 'ABSOLUTE_ROOT_AUTHORITY.json' EXACT_AUTHORITY_SHA
```

## Anaconda Prompt / CMD

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_paced_dispatch_v3.py --output "..\reports\S6C\20260910T123540Z\serial_paced_dispatcher\source_checks_v3_NEW"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_paced_dispatch_v3.py run --queue "ABSOLUTE_QUEUE.json" EXACT_QUEUE_SHA --authority "ABSOLUTE_ROOT_AUTHORITY.json" EXACT_AUTHORITY_SHA
```

