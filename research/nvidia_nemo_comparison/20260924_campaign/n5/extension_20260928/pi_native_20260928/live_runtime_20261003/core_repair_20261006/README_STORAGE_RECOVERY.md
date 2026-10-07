# Storage and startup recovery candidate

Purpose: make ordinary Stop/Discard/relaunch recoverable, admit finite SQLite
file sizes consistently in the GUI and worker, and keep storage startup errors
visible with capture disabled. This candidate also provides one atomic caption
projection transaction and bounded caption History reads. It uses the existing
recordings/history store and encoder galleries. Build28 remains immutable.

This file documents `storage.py`, `storage_support.py`, `launcher.py`,
`native_scope.py`, `worker.py`, `test_storage_recovery.py`, and
`run_host_storage_checks.py` in this candidate.
The normal application layout and backend menu are unchanged. The recovery
window appears only when normal Manager initialization fails.

## Inputs and outputs

Runtime inputs are the existing owned recordings root, StoragePolicy, validated
session/source policy, exact session UUID for an explicit Discard/Delete, and
bounded caption spans with stable parent IDs. The installed package still needs
its verified manifest, BINDING, dependencies, model assets, launcher envelope,
and gallery configuration. This folder alone is a source derivative, not a
deployable runtime or a completed native pass.

Outputs remain segmented processed float audio, replay WAVs, qualified physical
raw audio where admitted, paged SQLite History and revision events. Explicit
Discard removes its audio, transcript, spatial work files, index and allocation
rows. Only a minimal non-content deletion receipt remains. SQLite errors retain
their numeric extended code/name, primary code, operation and database path.
The recovery UI and stderr reporting do not write to the recording database.

The deterministic test takes no speech or production-data input. Its migration
fixture imports the preserved stabilization storage source. It creates
isolated temporary synthetic stores, prints unittest results, and removes the
temporary fixtures. It imports no model or audio-device package, starts no GUI,
contacts no device, and never fills a real filesystem. Native recovery of the
real database and portrait usability remain separate checks.

## Finite file allowance

`storage_support.sqlite_file_size_plan(root, metadata_bytes, policy)` includes
the existing main database and all SQLite sidecar extents. Its finite per-file
ceiling is the largest existing SQLite extent plus current free space above
the StoragePolicy reserve, capped at filesystem total capacity minus reserve.
The soft limit permits a larger index migration within actual available space;
it is not a predicted-metadata quota. Existing database bytes are not charged
again as future growth. Twice the predicted fresh metadata and an 8 MiB
journal/header margin must fit above the actual free-space reserve for
admission; scoped deletion uses bounded transactions.
The optional keyword `database_name='history.sqlite3'` admits only a bounded
single `.sqlite3` basename (ASCII letters/numbers/underscore/hyphen), allowing
the owned ASR segment ledger to share these checks via `asr_segments.sqlite3`.
Its journal/WAL/SHM are included identically; arbitrary paths are rejected.

`ensure_sqlite_file_limit` raises only the Linux soft RLIMIT_FSIZE when needed,
within the inherited physical-filesystem hard ceiling. The GUI
calls this before every writable SQLite connection. The worker uses the same
planner and retains the physical hard ceiling so its soft allowance can grow
with actual files. Windows uses the same capacity plan without changing OS
resource limits. No sidecar is removed or ignored.

The native GUI/worker bootstrap hard ceiling is filesystem total capacity minus
the existing 5 GiB minimum physical floor, rather than free bytes incorrectly
used as an absolute file length. The shared planner additionally applies the
actual StoragePolicy reserve (including its capacity fraction); the worker also
respects a smaller inherited hard ceiling. Actual free-space checks run before
writable operations. Low free space
can therefore reach the visible Manager recovery screen with capture disabled.
The envelope retains memory, ownership and package verification.

The old fixed 32 MiB database ceiling and duration-derived SQLite/terminal
metadata quotas are removed as ordinary-use limits under the user's explicit
authorization to remove arbitrary limits. Metadata ledger values now measure
cumulative charges; historical `limit_bytes` and session specs stay unchanged
as evidence. Exhausting one of those historical numbers cannot block speech,
Stop, Discard or cleanup diagnostics. Fresh reservation estimates help initial
capacity planning but are not enforced as database-writing quotas.

Bounded individual payloads, transaction batches, live rendering state and
queues remain functional working-set safeguards. Physical free-space floors,
actual memory budgets, finite file allowance based on real capacity and kernel
ownership remain. The independent external wrapper's small diagnostic-file
bound applies to its own receipts; it does not cap the recording database.

## Explicit deletion protocol

`store.discard(session_id)` requires an unkept stopped/failed/cancelled session.
`store.delete(session_id, confirm=True)` admits deliberate individual deletion
of a kept recording as well. Both take the selected session's exclusive kernel
lease. A live capture, replay or export lease prevents deletion.

Before any unlink, all children are validated with existing ownership,
registered-artifact and path checks. A small durable intent is written to
`recordings/deletions/<session-id>.json`, bound to the store ID, original status,
request kind, session ID and admitted directory names. The indexed session then
becomes `deleting`. Files are removed before their index entries; content rows
are purged in transactions of at most 128 rows. `owner.json` survives until the
media and index removals have committed. Finally the session directory is
removed, a minimal receipt is published under `deletion_receipts`, and the intent
is cleared. Repeated requests return the original completion receipt.
Audio/artifact index removal uses that same bounded purge, including raw-only
Keep cleanup; it never commits an entire large segment/artifact corpus in one
DELETE transaction.

Writable startup resumes only these persisted explicit intents. It never scans
or automatically deletes arbitrary orphan/failed/kept sessions. At most 64
pending intents are handled in one startup batch; excess or malformed work is
reported through recovery with capture disabled. Unknown children, symlinks,
reparse points, hard links, wrong store IDs and changed ownership fail closed.
An interrupted retry cannot resurrect deleted audio or transcripts.

`deletion_pending(session_id)` verifies the pending intent for the application's
Retry control. A `deleting` status alone is insufficient authorization.

The old library Discard retained transcript/evidence; this candidate intentionally
changes that behavior to the user's complete temporary-session removal contract.
Existing kept recordings are unchanged. No automatic legacy orphan migration is
included. An earlier partially deleted session needs exact-state inspection and
a separately authorized, scoped recovery plan.

## Atomic caption API

`replace_caption_projection(session_id, parent_key, parts,
projection_revision=None, projection_source_start_sample=None)` accepts at
most 256 parts / 256 KiB total. Each part
has exactly `caption_id`, `start_sample`, `end_sample`, `text`, `speaker`,
`provisional` (bool), and `provenance` (object). The parent ID is at most 128
characters. `provenance.supersedes_parent` is absent or equals that parent.

One transaction inserts/updates changed parts, retires absent children belonging
to that exact parent, and preserves their old revision events. Identical
redelivery creates no event or metadata charge. An explicit positive presentation
revision is monotonic: older projections are ignored, conflicting equal revisions
are rejected. This revision is independent of ASR text revisions so delayed
speaker/punctuation decisions can update unchanged words. With `None`, only
changed payloads advance the presentation revision.

Migration adds nullable `captions.projection_parent`, default-zero
`projection_order`, nullable `projection_source_start`, an indexed parent/source
order and `caption_projections` with a stable parent source anchor.
Existing session specifications and allocation ceilings are unchanged. Existing
caption rows retain their content and use their caption ID as the ordering parent.
The same bounded read APIs support an external read-only Saved store with the
legacy schema using caption ID/zero ordinal, without migrating that store.
Raw revision events remain available; this API changes the visible projection,
not the historical recognition evidence.
New projections order by parent source anchor, parent key, native token ordinal
and caption ID. The stable anchor is the earliest native parent/child source
sample, optionally supplied explicitly, and retained across later refinements.
This keeps a parent's tokens in order when honest coarse windows and aligned
child windows coexist. Individual child source clocks are unchanged. No
retrospective legacy row backfill is performed.

`latest_captions` remains bounded and returns source/parent/span order.
`caption_page(session_id, limit=40, before=None)` returns chronological bounded
older pages with an opaque cursor. `caption_parents(session_id, parent_keys,
limit=120)` refreshes at most 80 frozen parent IDs and reports `truncated` if
their current partitions exceed the output bound. The caller must preserve its
existing scroll anchor when truncation occurs. No whole-session transcript is
loaded by these APIs.

## Run the isolated checks

Use the existing project interpreter. No installation or environment changes
are needed. Follow the parent workflow's permission to run one host process at
a time. `run_host_storage_checks.py` registers the exact Windows PID/creation
FILETIME on CPU14 before project imports, creates durable/readback-verified
source backups and separate restored copies, then runs the tests in that same
process. Inputs are these candidate sources, unchanged profiles, the preserved
historical storage source and a fresh nonexistent private `--output` directory.
Outputs are bounded owner/scope/source/test/result/exit receipts and synthetic
fixture data. Successful tests close/remove their synthetic fixture directories;
failed output directories remain evidence and must not be reused or overwritten.
No production database, galleries, SSH, models or display are accessed.

PowerShell, from any directory:

```powershell
$py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$repair = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$label = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/core-storage-host-' + [guid]::NewGuid().ToString('N')
& $py -B "$repair/run_host_storage_checks.py" --output $label
Get-Content -LiteralPath "$label/RESULT.json"
```

Command Prompt:

```cmd
set "PY=C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe"
set "REPAIR=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006"
rem Select a NEW private label; never reuse a prior run directory.
set "OUTPUT=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/core-storage-host-CHOOSE-UNUSED-LABEL"
"%PY%" -B "%REPAIR%/run_host_storage_checks.py" --output "%OUTPUT%"
type "%OUTPUT%/RESULT.json"
```

Anaconda Prompt uses the same Command Prompt commands above. The explicitly
selected interpreter is authoritative; the active Conda environment need not
provide SQLite or model dependencies for these standard-library checks.

After the interpreter exits, independently check the registered PID and exact
creation FILETIME are absent, and read back the exit/source receipts. The
runner uses host free-space floors (C: 50 GiB, G: 75 GiB), 128 MiB of fixture/
receipt allowance, 256 KiB per source/receipt and 64 KiB test log. Its 120-second
deadline check bounds completed runs; the supervising workflow must enforce
exact-owner termination and closure if a broken test hangs. These are temporary
verification budgets, not deployed recording quotas.

The checks cover historical-quota removal and kept-data schema migration,
read-only legacy Saved captions without database-byte changes,
completed Discard isolation/idempotence, interruption after
audio removal/database purge/owner unlink/completion receipt failure, held
leases, unrelated-child/wrong-store rejection, PRAGMA connection cleanup and
extended errors, independent lease release and primary-error preservation,
source-order paging, atomic partial-word correction, genuine
repetition preservation, duplicate projection delivery, transaction rollback,
finite file admission and the capture-disabled initialization branch. These are
contracts and fault injection, not model accuracy or physical GUI usability.
The observed numeric regression uses a synthetic 35,889,152-byte database and
41,552-byte journal: it must exceed the previous 33,554,432-byte GUI limit,
receive a larger finite allowance and retain every journal byte. It does not
open or recover the real native hot journal.

Verified host result on 2026-10-06: **21 tests passed**, 10.693 seconds of test
time / 11.078 seconds for the registered runner. Receipts are under the private
`audit-preparation/core-storage-host-e375a8255c154ed3b9e1ca6275092712` label.
PID 66396 / creation FILETIME 134357782115383269 was independently absent after
exit. Eleven source backup/restore/hash comparisons passed, fixtures closed,
and 723,717 bytes of output preceded the independent closure receipt. The
README's result paragraph was updated after that run. Subsequent required
shared ASR-ledger admission and coarse/aligned parent-order integration add
two new fixtures. Their final **23-test run passed** on 2026-10-06, 12.866
seconds of test time / 13.234 seconds for the registered runner, under
`audit-preparation/core-storage-host-c0710b73f88e43a2914d89965ea1405c`.
PID 69452 / creation FILETIME 134357789048818646 was independently absent after
exit. Eleven source backup/restore/hash comparisons passed, fixtures closed,
and 740,413 output bytes preceded the independent closure. Runtime/test code
is frozen after that pass; this maintained result text is updated afterward.
The earlier `5054c82628f24fd29d71e1cd4d6ca948` failed label
and its independent closure remain unchanged: one test interruption hook lacked
the helper's new optional `kind` argument, fixed only in test code before the
fresh passing run. No native test, production-database repair or model accuracy
claim follows from this host result.

## Retained-data repair and deployment

Before activating a schema/file-limit derivative, preserve a consistent backup
of retained data. A healthy live database can use SQLite's backup API; copying
its active main file alone is insufficient. For a closed database with a hot
journal/WAL, preserve the complete main/sidecar set and independently restore
and recover a copy before allowing the original to recover. Do not delete a
journal, turn off integrity checking, or open a changing database as immutable
to force a clean-looking result.

The parent repair workflow performs the actual native backup, copied recovery,
ownership checks, selected-session cleanup, packaging and activation. Include
`storage_support.py` and all changed/new members in the new immutable package
inventory. Never overwrite build28 in place. Native tests must exercise repeated
Start/Stop/Discard/Exit/relaunch and controlled interruptions against isolated
fixtures, then verify the portrait window and preserved kept data. No sustained
or accuracy qualification follows from the deterministic checks alone.

References: [SQLite result codes](https://www.sqlite.org/rescode.html),
[SQLite consistent backup](https://www.sqlite.org/backup.html), and
[SQLite corruption causes](https://www.sqlite.org/howtocorrupt.html).
