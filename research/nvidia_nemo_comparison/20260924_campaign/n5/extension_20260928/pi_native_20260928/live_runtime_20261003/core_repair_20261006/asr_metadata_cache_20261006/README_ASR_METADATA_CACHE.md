# Private ASR metadata cache candidate

This is a candidate over sealed build33. The corrected 17 host checks passed;
both failed fixture runs are preserved. No package has been built or staged from
this directory. Native hour06 closed with speaker backlog, without MemoryError. It makes no native throughput,
quality or native qualification claim.

## Purpose and scope

`asr_segment_runtime.py` currently reopens its per-session `asr_segments.sqlite3`
for every utterance-tagged event, including a label revision and the recursive
display event. This candidate reuses unchanged parent metadata without repeating
that connection/PRAGMA/SELECT/join work. It preserves every durable write, model
call, source window, event timestamp, parser and physical-capacity guard. History,
caption storage and other recordings use a different `history.sqlite3`; event
segments are different files as well. Their writes do not invalidate this cache.

`asr_metadata_cache.py` stores only immutable SQL metadata JSON strings, group
IDs and punctuation flags. Every returned dictionary is parsed afresh, so caller
annotations cannot mutate the cache. The real OrderedDict allocation and retained
keys/strings/tuples/cost integers are charged, with 4 KiB conservative fixed
overhead for the helper instance/scalars and four bounded filesystem observations.
The cache has an 8 MiB charged extent and 4096-entry eviction boundary. Oversize
metadata, unusual ID shapes, eviction or a fault always use the existing SQL;
these limits never reject recording content or cap corpus length/population.
The group-invalidation key list is bounded to 4096 references. SQL-return/JSON
working memory remains subject to the unchanged process envelope.

## Correctness, failure and ownership

The existing ledger RLock covers lookup, SQL fallback and cache publication.
`record` invalidates its actual stored parent only after successful commit. One
indexed parent lookup inside that write transaction preserves the inherited
seq-conflict behavior even when supplied IDs differ from the stored parent;
`close_group` and
`mark_punctuated` invalidate retained members of that group after commit.
`claim_final` and `save_patches` do not change metadata's selected columns, so their
successful writes refresh the file stamp without evicting unrelated parents.
Group-ID binding coercions outside the native string-ID shape clear the cache
after commit rather than guessing which textual key was affected.

A read, write or commit failure fences cache hits. SQL remains authoritative, including
when a commit succeeded but a later failure made its outcome uncertain. A later
successful owned commit clears and releases the fence. Optional cache allocation
failure also fences the cache and preserves a valid SQL result. The original FULL
synchronous transaction and rollback behavior is retained.

Cache-hit admission still checks that the ledger file exists. Its main file and
named rollback/WAL/SHM sidecars are observed by lstat (no payload read). Unexpected
inode, extent, mode/link or timestamp drift clears the cache and falls back to SQL;
changes during a SQL read prevent admission of that snapshot. Our successful
tracked commits refresh this stamp after targeted invalidation, so normal writes
to unrelated ledger parents/tables preserve cache usefulness. Filesystem stamps
are observations, not atomic defense against an unauthorized concurrent writer.
The admitted runtime has one SegmentLedger instance shared by its ASR/PnC lanes
inside an owned session. A second external writer remains outside that ownership
contract. No cache is shared across sessions or process lifetimes.

The sealed build33 caller audit finds the ledger constructor only in
`SegmentedAsrMixin._asr_loop` (original line 299), at the unique session directory.
Its five mutation methods are the only packaged writers of these four tables:
`pieces`, `closed_groups`, `patches` and `punctuation`. The ASR facade calls `record`
(line 253), final publication calls `claim_final` (330), and spoken-group/PnC work
calls `close_group` (340), `save_patches` (374) and `mark_punctuated` (380). All
share the same ledger object/RLock. `SessionStore` separately binds
`history.sqlite3` at `storage.py` line 307. No history, GUI observer or journal
writer opens this ASR ledger through a second packaged code path.

## Inputs and outputs

Runtime inputs/outputs are the original SegmentLedger methods and SQLite schema;
`metadata(parent)` returns exactly the same dictionary/None and punctuation flag.
The helper adds no product control or tunable and retains no raw transcript/audio.

`test_asr_metadata_cache.py` has 17 focused synthetic cases: SQL/reference equality,
200-read query elimination across 20 unrelated metadata commits, private returns,
parent/group invalidation, unrelated
table commits, rollback/uncertain commit, concurrent commit fencing, filesystem
drift/removal/replacement, real cache extent/eviction, binding/shape fallback,
allocation failure, read faults on previously cached parents, invalid stored JSON
and unchanged model/clock/SQL guards.
The query-count fixture records the avoided read connections; it does not claim
a measured native speedup. Cache hits still perform bounded file observations and
fresh JSON parsing, while every `record` has the added indexed parent lookup.
The original build33 ledger is an independently pinned oracle, not an edited file.
These are host-only fixtures; they do not load a model or touch retained data.

`run_host_asr_metadata_cache.py` is a proposed registered CPU14 runner. It writes
REGISTERED_OWNER before project imports, backs up/restores every source, uses a
fresh private fixture directory, limits output, and records RESULT/SOURCE_CLOSED/
SOURCE_UNCHANGED/HOST_EXIT. Source/manifest/restore reads admit file size before allocation and read at most
2 MiB plus one rejection byte, including after-check source verification.
Natural process exit and an independent OS absence check must produce HOST_CLOSED
before a result can be admitted. A printed PASS or
HOST_EXIT alone is not closure proof. Host checks are now complete; another run
needs a concrete changed-code/failure reason and coordinated owner slot.
Native/package execution remains unauthorized.

The initial host evidence is preserved at campaign-local
`audit-preparation/asr-metadata-cache-host-839ea93850af43948526b497333f0f1a`.
All 17 cases failed in setup because production's default 5% reserve on the host
G: volume yielded zero admitted writable bytes. This exercised the unchanged
storage guard, not cache behavior. CPU14 PID 17356, creation FILETIME
134357960973800452, exited naturally with code 1 and was independently absent;
all 14 source/backup/restore/current pins were exact. The pre-return receipt says
fixture_closed=false; it is preserved unchanged and cannot be admitted.

Only the synthetic fixture policy is corrected: 5 GiB actual reserve, fractional
reserve zero, and unchanged independent runner floors of 50 GiB on C: and 75 GiB
on G:. TemporaryDirectory cleanup is registered immediately so setup failures
close before the runner's closure check. Runtime policy and physical guards are
unchanged. Initial test/README bytes and their independent restores are in
`preserved/*host17_initial*`; no failed receipt or source proof is overwritten.

The second host evidence is preserved at
`audit-preparation/asr-metadata-cache-host-434557dc00c84fc3884c3bcf898f5ee7`.
Fifteen cases passed, including 200 exact rows with one candidate SQL read versus
200 reference reads across 20 unrelated commits. The two external-write fixtures
passed their assertions but failed cleanup because SQLite's connection context
manager commits without closing the connection. CPU14 PID 28328, creation FILETIME
134357961921492380, naturally returned code 1 and was independently absent; all
14 source triples were exact. Its failed receipts and two synthetic directories
remain untouched. The fixture-only correction explicitly closes these two
connections before cleanup; production code is unchanged. The second tested
test/README sources and restores are preserved as `*host17_reserve*`.

The final corrected run passed all 17 cases with zero failures/errors/skips in
2.719 seconds. Query reduction is measured as one read connection versus 200
reference connections for 200 exact normalized rows across 20 unrelated metadata
commits. No native throughput is measured. All 14 source backup/restore/current
pins were independently exact, fixtures were empty, and no model/native code ran.
CPU14 PID 42004, creation FILETIME 134357962408937611, naturally exited code 0
and was independently absent. Evidence is at campaign-local
`audit-preparation/asr-metadata-cache-host-873314e3cfa746ee891105ca32d0d271`:

- RESULT SHA256 `76a8e4f0bfcd99b729e7f055d0ecd3d9de68ffc7d153a5f252e6a86937e45c47`
- HOST_CLOSED SHA256 `5d307de968239b9c828cc1b7a954bb9a38d5da46fdd41abee0519e3985f2f7ff`
- SOURCE_CLOSED SHA256 `2c8266f12ee0cf26a89f68299c7ddc94a62eef4ac1049638c6869a741f18d36d`

The runtime pair and runner did not change across these checks. This README's
evidence paragraph was updated after closure; its prior tested bytes remain in
the host source preservation. A later builder pins the current maintained README
separately while requiring exact tested runtime/test/runner bytes.

## PowerShell

Use the pinned host interpreter, not the WindowsApps `python` alias. Set paths:

```powershell
$py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$task = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/asr_metadata_cache_20261006'
$q = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$label = 'asr-metadata-cache-host-' + [guid]::NewGuid().ToString('N')
& $py -B "$task/run_host_asr_metadata_cache.py" --output "$q/audit-preparation/$label"
```

Run only after root assigns the single host CPU14 slot. Capture the actual early
owner, wait for natural exit, recheck the exact PID/creation FILETIME independently,
and write HOST_CLOSED only after absence is established. Preserve failed receipts;
use a fresh label for any authorized retry. Do not run this on the Pi.

## Command Prompt and Anaconda Prompt

Both use the exact same interpreter. Choose a fresh 32-lowercase-hex UUID suffix;
the destination must not already exist. `conda activate` is not required.

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_TASK=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\asr_metadata_cache_20261006"
set "JP_Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
set "JP_LABEL=asr-metadata-cache-host-REPLACE_WITH_FRESH_32_HEX_UUID"
"%JP_PY%" -B "%JP_TASK%\run_host_asr_metadata_cache.py" --output "%JP_Q%\audit-preparation\%JP_LABEL%"
```

The candidate's original ledger SHA256 is
`c5d474e86b6a38754dac4f86bcec6e244950822a2781e202a7362e05ac57219c`.
`preserved/asr_segment_runtime.build33.py` and its `.restore` are exact source
preservation copies; they are local provenance, not runtime package inputs.
Update this README with actual authorized evidence if the candidate is tested.
