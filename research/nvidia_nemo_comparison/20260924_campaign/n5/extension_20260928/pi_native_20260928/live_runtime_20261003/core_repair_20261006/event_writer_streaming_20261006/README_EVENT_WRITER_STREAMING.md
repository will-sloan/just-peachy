# Streaming event writer draft

This separate draft reduces avoidable event encoding allocations while retaining
the frozen build31 logical event stream and compact-record format. It does not
modify build31/build32, run native code, change models, relax durability, change
the backlog gate, or raise any runtime memory limit. Native qualification is
pending. The host checks described below require a coordinated host slot.

## Purpose and actual failure scope

Closed native hour05 on build31 failed after 922.9 source seconds, or 14,766,400
samples. Its compact receipt records `complete=false`, `MemoryError()`, 54,245
logical records and 552,700,062 logical bytes. The physical writer had zero
pending bytes and accepted/completed 196,116,380 bytes in 24 segments. This is a
failed session; its external process closure and complete evidence mirror do
not make its internal failed writer handle complete.

The numeric-only unit monitor observed virtual memory near the finite 768 MiB
address-space ceiling: the last current peak was 803,078,144 bytes against
805,306,368, and the recorded virtual peak left 81,920 bytes. Available physical
RAM at that sample was 1,127,251,968 bytes. Monitor elapsed times are not the
source clock. The original failing allocation line is not available in the
receipt. These observations support address-space pressure; they do not prove
which codec or sink allocation failed, or explain all gradual resident growth.

Static inspection found that the old writer retained canonical event bytes,
encoded a full wrapper before deciding to use a patch, separately encoded the
display payload, concatenated a newline for the digest, and converted selected
bytes to text before the sink encoded them again. Segment rotation itself only
flushes/fsyncs/closes the stream; it does not reread or compress whole segments.

## Files, inputs and outputs

* `event_compaction.py` hashes/counts canonical JSON with `JSONEncoder.iterencode`
  using its C encoder fast path (`_one_shot=True`),
  tries the patch first, and builds a complete full wrapper only when selected.
  Its input remains a bounded JSON event string/byte record. It emits exactly
  one immutable compact-record byte item, with staged digest/cache state
  committed only after queue acceptance. `prepare_text` retains strict JSON,
  UTF-8 byte accounting and the original leading UTF-8 BOM behavior.
* `runtime_support.py` adds `SegmentedText.write_bytes(bytes)`. It retains the
  existing record and queue checks, FIFO item publication, byte accounting,
  free-space guard, failure callback, segment fsync and closure/index logic.
  `write(str)` still returns its input character count. The new byte method
  accepts exact immutable `bytes` and returns its byte count.
* `test_event_writer_streaming.py` contains 14 synthetic checks. Its read-only
  reference input is the exact frozen build31 codec. Checks compare canonical
  records and full logical digests, revisions/session changes/patch fallback,
  invalid inputs, exact record boundaries, private reader cache, immutable FIFO
  submission, queue-full rollback, failed sink admission, and successful drain
  and roundtrip. A 300 KiB repeated-display fixture compares traced preparation
  allocation peaks. That same case records old/new wall and thread-CPU time for
  20 identical revisions of a large-text display and a synthetic 59-word-span,
  45-segment display with nested identity snapshots. The latter counts come from
  a numeric/schema-only inspection of one 284,086-byte mirrored full display;
  all fixture text, IDs and numeric values are synthetic. These measurements
  describe codec preparation rather than native model memory or full-session
  throughput. The fixture rejects a draft CPU increase above 20% plus 5 ms total
  timing tolerance; the coordinator still reviews the actual measured numbers.
* `run_host_event_writer_checks.py` runs that suite in one Windows process pinned
  to CPU14 before any project import. It takes `--output` pointing to a fresh
  nonexistent `event-writer-host-<32 lowercase hex characters>` directory in the
  campaign's `audit-preparation` directory. It pins/backups/restores eight inputs
  before imports, rejects changed source origins, and uses only private synthetic
  event files. No database, private audio, gallery vectors, model or SSH is read.

The runner emits `REGISTERED_OWNER.json`, `HOST_SCOPE.json`, eight source backups
and independent restores, `SOURCE_CLOSED.json`, `TEST_OUTPUT.txt`, `RESULT.json`,
`SOURCE_UNCHANGED.json` when all source checks close, and `HOST_EXIT.json`.
`RESULT.json` uses `just-peachy.event-writer-streaming-host.v1` and reports all
failure/error/skip counts, fixture closure and numeric traced preparation peaks.
The temporary fixture directory must be empty at closure. `HOST_EXIT.json` is
a pre-return receipt; the operator must separately prove natural return and
exact registered owner absence and write `HOST_CLOSED.json`.

## Preserved bounds and compatibility

The canonical flags remain `ensure_ascii=False`, `sort_keys=True`, compact
separators and `allow_nan=False`. Full/patch bytes, sequence, payload SHA,
logical SHA including newlines, strict smaller-patch comparison, session/base
identity and complete/partial read rules remain unchanged. The reader still
deep-copies reconstructed payloads so consumer annotations cannot mutate the
next patch's base. Codec preparation retains one detached parsed event and one
prior display payload; it does not keep cumulative session history.

The existing 1 MiB event/parser bound, 4 MiB pending-byte queue, 512 item queue,
8 MiB segments, finite patch depth/operation bounds and physical free-space
guard remain. Cumulative disk estimates remain accounting rather than corpus
quotas. Encoding sends UTF-8 fragments of at most 4096 characters to hash/output
streams. The C encoder retains one temporary canonical JSON string; it is not a
Python loop over every JSON token. Strict parsing still allocates a complete
event tree. This draft reduces redundant full-event copies; it does not claim that
every producer allocation is constant size or that the failed hour is fixed.

The exact source inputs copied before edits were build31
`event_compaction.py` SHA256
`4ad7255459b7aadbbee1c1bd498a6f1402e3ba60e83db0386a6a9bf10f28e206`
and `runtime_support.py` SHA256
`b31cc219a1dded71bc2393190c79a9e93a8bfcaff206c5c69d3c7ee056a24999`.
The parent manifest is
`4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767`.
Only the draft runtime pair is intended for a later reviewed package; the test
and runner remain host-only. No package is generated by these commands.

## PowerShell: coordinated host check

Use the existing project interpreter; do not install packages or use the
WindowsApps alias. Confirm the root coordinator has released one host slot.
The runner's finite prepared-evidence allowance is 16 MiB, with a 600 second
scope and physical host free-space floors of 50 GiB on C: and 75 GiB on G:.

```powershell
$taskRoot = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/event_writer_streaming_20261006'
$pythonPath = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$auditRoot = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation'
$checkOutput = Join-Path $auditRoot ('event-writer-host-' + [guid]::NewGuid().ToString('N'))
& $pythonPath -B (Join-Path $taskRoot 'run_host_event_writer_checks.py') --output $checkOutput
$naturalExit = $LASTEXITCODE
$checkResult = Get-Content -LiteralPath (Join-Path $checkOutput 'RESULT.json') -Raw | ConvertFrom-Json
$registered = Get-Content -LiteralPath (Join-Path $checkOutput 'REGISTERED_OWNER.json') -Raw | ConvertFrom-Json
if ($naturalExit -ne 0 -or $checkResult.status -ne 'PASS') { throw 'Preserve failed raw evidence; do not admit it' }
if (Get-Process -Id $registered.pid -ErrorAction SilentlyContinue) { throw 'Registered PID still present; exact closure requires separate review' }
$closed = @{owner=$registered; natural_exit_code=$naturalExit; os_process_absent=$true; independent_os_check=$true}
$closedBytes = [Text.Encoding]::UTF8.GetBytes(($closed | ConvertTo-Json -Depth 10 -Compress))
$closedPath = Join-Path $checkOutput 'HOST_CLOSED.json'
$closedStream = [IO.File]::Open($closedPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try { $closedStream.Write($closedBytes,0,$closedBytes.Length); $closedStream.Flush($true) } finally { $closedStream.Dispose() }
if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($closedPath)) -ne [Convert]::ToBase64String($closedBytes)) { throw 'Closure readback differs' }
$checkResult | ConvertTo-Json -Depth 10
```

The owner receipt includes both PID and creation FILETIME. The conservative
PowerShell check above only admits an absent PID. A reused/present PID requires
the coordinator's exact FILETIME comparison; do not kill unrelated processes.

## Command Prompt

Choose a new private label, then inspect the actual result. Run the same
PowerShell independent closure procedure above after this command returns;
record its actual exit status before running another command.

```cmd
set "JP_EVENT_TASK=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\event_writer_streaming_20261006"
set "JP_EVENT_OUT=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\event-writer-host-0123456789abcdef0123456789abcdef"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%JP_EVENT_TASK%\run_host_event_writer_checks.py" --output "%JP_EVENT_OUT%"
echo %ERRORLEVEL%
type "%JP_EVENT_OUT%\RESULT.json"
```

The example label must be replaced if it already exists. Do not rerun against
the same output or delete failed receipts to reuse a label.

## Anaconda Prompt

No conda environment change or dependency download is needed. Use the explicit
existing project interpreter in the Command Prompt commands above from the
Anaconda Prompt. It does not depend on `conda activate` or whichever `python`
appears on PATH. The same inputs, fresh-output requirement and independent
owner closure apply.

## Current validation status

Independent source review found no concrete byte/choice/queue-body discrepancy.
The authorized 14 host checks passed with zero errors/failures/skips in 3.156
seconds, with all eight source backup/restore/current-byte pins exact and the
fixture directory empty. The CPU14 owner PID 53436, creation FILETIME
134357923812286188, returned naturally with exit code 0; the separate
PowerShell check confirmed its exact absence. No native/model code ran.

Evidence is at campaign-local
`audit-preparation/event-writer-host-649e50fbed2a45d1865aefae87f80b3f`:
`RESULT.json` SHA256
`11d11396ac5bf239bdac983646e3d01369b624a54b6c57b277a2b0c9bbf4c337`,
`HOST_CLOSED.json` SHA256
`4dbf7abc86608cb0284d673f5fc80bf71468e9d70810e375015461a06b2d50a0`.
This README's evidence paragraph was added after that process closed; all four
runtime/check/runner source files retain their tested bytes. A future builder
must pin the current README separately from the tested source pins.

Exact compact records and logical digests matched the frozen reference. Traced
preparation peak was 1,868,863 bytes before and 961,646 bytes after, a reduction
of about 48.5%. Twenty large-text revisions took 0.0625/0.046875 seconds of
reference/draft thread CPU and 0.06329/0.04710 seconds of wall time. The nested
59-span/45-segment synthetic workload took 1.125/1.03125 CPU seconds and
1.20167/1.11682 wall seconds. Its 696,677-byte event is deliberately larger than
the observed 284,086-byte native example; its arrays/schema categories follow
the observed shape, but it is not a replay of that private event. These two
measurements showed no CPU regression. They do not establish sustained native
throughput, backlog recovery or a completed hour. Native qualification and any
future packaging still require the root coordinator's later review.
