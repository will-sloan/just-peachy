# Installation, health and recovery

Current build35 scope: build35 is activated through the Just Peachy shortcut.
Opening stays idle with capture off. Choose one of six backend combinations,
Live microphone or Saved WAV, then Open Application and a Mode. Eleven Mode
policies are visible; backend, identity policy and calibration are separate.

Ordinary Pyannote + ReDimNet Start captured 12.5 s and completed Stop and the
selected full Discard in normal03. That whole check FAILED its later Settings
observer. Separate exit-only05 passed idle Open Application, Settings and Exit
with no Start, capture, models or worker launch. These are distinct scopes.
Live53 passed quiet capture after one verified recovery; Saved54 processed C24
speech with 137 indexed parts, 40 text rows and 117 embedding queries.

Hour08 completed 3600 s / 57.6M samples and all 20 source/model/closure gates.
Backlog grew to 495.360 s; source-to-EOF took 4090.959 s. Completion passed,
but sustainable real-time operation did not. Speech/name accuracy, natural
conversation and biometric calibration remain unqualified or UNCALIBRATED.

Normal live uses manual Stop and storage capacity without arbitrary duration,
recording, people, reference or slot counts, or a fixed ordinary backlog cutoff.
Actual memory/AS/free-space, finite capacity-derived file/drain allowances,
bounded queues, source/lease/owner, I/O and cleanup guards remain. Individual
lane delay labels are unavailable; aggregate backlog remains in health metadata.
Model geometry, thresholds and calibration math are unchanged.

## Startup and healthy use

The single Just Peachy shortcut opens the six-row chooser, then the portrait
Mode/People/Settings application. Opening stays idle/capture-off; Start itself
authorizes live listening. Enrollment/gallery consent is separate. Login
autostart remains disabled. Existing microphone readiness recovery is limited
to its exact guarded fault/owner path, with one conditional continuation;
it does not loop firmware resets or qualify speech models.

Stop waits for source/model/worker drain and closure before Save/Discard.
Return to backend combinations closes the controller and returns idle to the
chooser. Exit closes the launcher; reopening obtains a fresh owned envelope.
Manual session duration and GUI idle lifetime are different. Actual storage,
source/queue-health, finite drain/cleanup and hardware faults can stop safely. Ordinary manual Stop has no fixed backlog cutoff.

Recording History is UUID-based and paged. Availability depends on measured
storage capacity, not four slots, a recording-count cap or duration-derived
SQLite/text quota. Segmented files and bounded working sets remain. Physical
free-space reserves and finite capacity-derived per-file limits still apply.

## If startup reaches recovery

Manager initialization failures show a recovery window with capture disabled
and explicit SQLite/I/O diagnostic details. Retry reattempts the owned manager
initialization; it does not silently erase sidecars or arbitrary recordings.
Diagnostics preserve extended SQLite code/name, operation and database path
without transcript words or vector contents. Preserve the original failure.

Writable startup resumes only persisted explicit Discard/Delete intents bound
to the correct store/session. A status such as failed/deleting/discarded, an
orphaned directory or a missing audio flag is not independent deletion authority.
Unknown children, changed ownership, symlinks/reparse points, hard links or
held capture/replay/export leases block the action rather than selecting another
session. Kept sessions require deliberate individual Delete.

## What complete Discard means

An explicit request takes the selected session's exclusive lease and validates
its owned artifacts before unlink. A durable store-bound intent is published;
the index becomes deleting. Media/artifacts are removed before bounded index
purges. owner.json remains until content/index removal commits, then the empty
session directory is removed and a minimal non-content receipt completes the
intent. Interrupted retries use that same intent; exact repeats are idempotent.

This removes temporary audio, transcript, captions/revisions, spatial work and
allocation/index rows. It does not mutate another UUID or automatically clean
unrequested legacy orphans. Old kept evidence is not retrospectively backfilled.

## Capacity and the known cleanup edge

SQLite considers main/journal/WAL/SHM extents. Its expanding finite file ceiling
uses existing extents plus free bytes above StoragePolicy reserve, capped at
filesystem capacity minus reserve. Linux can raise a soft allowance only within
the inherited finite physical hard ceiling. Existing bytes are not charged
again as future growth. Logical quota meters remain accounting only.

The shared planner needs 2 * metadata_bytes + 8 MiB above reserve before every
writable LocalStore connection. At default metadata 0, reserve + 8 MiB is needed
even for writable reads/deletion validation. Below it, Discard can fail before
its first unlink; the ASR ledger's 4 MiB planning input requires 16 MiB above
reserve. This physical cleanup edge is **not repaired by logical quota removal**.
Do not promise that near-full storage always allows automatic cleanup. A
separately scoped recovery must preserve the sidecars and intended session.

## Database recovery and rollback

Back up the exact closed database and all present sidecars before any repair.
A completed selected-release-and-user-data backup needs independently verified
member bytes/hashes and actual source/owner closure; a census, copied subset,
old embedded backup or progress indicator is not COMPLETE.

Normal SQLite hot-journal recovery first passed on an independently restored
host copy, leaving original captured PC bytes unchanged. After accepted full
backup12, actual Live34 SessionStore opening recovered the native database:
35,889,152 bytes plus a 41,552-byte journal became36,171,776 bytes with no
journal/WAL/SHM; quick_check returned ok and projection columns were present.
No manual journal clear occurred. This is actual store-opening recovery after
full backup, separate from the earlier host-copy result and from generic crash
or power-cut durability. Explicit UI Discard then removed only its new selected
session, with zero rows across nine selected tables and idle chooser/app relaunch.

Never manually remove a hot journal/WAL/SHM, open an immutable URI to hide
recovery, overwrite a release in place or clear owner fences to force Start.
Use the exact reviewed package/action and fresh boot/owner/backup receipts.
No copy-only success becomes backup completion. Do not replay a consumed
stage/activation/recovery payload or substitute historical acceptance.

Build28 and older immutable releases/data remain rollback points. Restore only
the exact previous desktop/control bytes verified by the matching activation
before/restore receipts, after source/helper/cgroup closure. This draft neither
activates a candidate nor manufactures a rollback/backup-completion receipt.

## Evidence and technical run guidance

Host storage 23, caption/ASR 36, identity 28 and caption-handoff 5 passed their
declared synthetic/pinned scopes with backups/restores and exact owner closure.
Live34 and later checks retain bounded native recovery/Discard/relaunch evidence. Build35 has quiet Live53 and nonempty Saved54 speech/UI checks, normal03 capture/Stop/Discard subpasses and separate idle Exit05. Hour08 completed source/drain/closure with growing lag; sustainable real-time remains unqualified. Physical power-cut/coldboot durability and
arbitrary crash recovery do not follow from normal Stop/Exit.

Technical purpose, inputs/outputs and PowerShell/CMD/Anaconda commands are in
the candidate READMEs: README_STORAGE_RECOVERY, README_DATABASE_RECOVERY,
README_CORE_BACKUP_V2, README_CORE_STAGE_V2 and README_CORE_NATIVE_VALIDATION.
Operator startup is the desktop shortcut; native maintenance uses the root's
guarded dispatcher, not standalone recovery commands pasted from historical
examples. See MODE_GUIDE and CORE_REPAIR_TECHNICAL_NOTES for identity/caption limits.
## Current source and preserved recovery evidence

Build35 is activated through the current capital/spaced Just Peachy shortcut. Its selected
[source map](../extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/current_build35/SOURCE_MAP.md)
identifies current code and the separate installer; source presence is not
activation or a backup.

Backup14 was complete at its own census:2990 files/684159787 bytes, independent
hash/readback and exact68815 closure. COMPLETE SHA256:
9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e.
It predates later hour05 changes and is not called a fresh post-failure backup.
Rollback28 and existing kept data/galleries remain preserved.

Hour05 on31 closed FAILED at 922.9 source seconds. Its complete external mirror
is distinct from the incomplete internal compact writer. The writer reported
MemoryError; physical available RAM remained about 1.1 GB while VmPeak approached
the finite 768 MiB AS ceiling. D1 backlog pressure also existed; exclusive
allocation/stop ordering is unproven. Keep that failure and its original scope.
Do not treat a capacity-driven store or a raised finite candidate AS ceiling as
proof of successful recovery or sustained operation.

## Current desktop syntax erratum

The activated shortcut is /home/peachyprototype/Desktop/Just Peachy.desktop. In PowerShell, CMD and Anaconda Prompt quote --desktop "/home/peachyprototype/Desktop/Just Peachy.desktop". The lowercase example in the preserved original normalGUI35 README is historical. V2 selects six metadata reserves and preserves the original32MiB FSIZE; it changes no runtime policy. Do not rerun closed acceptance as ordinary use.
