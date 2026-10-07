# Caption, identity and resource contracts

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

Use the [selected source map](core_repair_20261006/current_build35/SOURCE_MAP.md)
to locate actual current package Python, controls/profiles and maintained READMEs.
The source-only mirror is distinct from its separately hashed deployment installer.
[Pipeline notes](CORE_REPAIR_PIPELINE_NOTES.md) cover all six unchanged model
combinations; operator use/Modes remain in the completion guides.

## Current shared changes and evidence scope

Caption parent partitions retire stale children atomically, preserve native
outer-parent source/token order and allow delayed presentation revisions without
resurrecting old source rows. Immediate partials, genuine spoken repetitions,
actual BPE continuation and bounded pause/Stop PnC retain source provenance.
Detailed arithmetic and limits follow.

Build31 derives the hash-bound original N2 revision method by changing two
snapshot calls and current-pair cache cleanup only. Keyed revisions copy existing
canonical identity fields for one parent under the presentation lock; global
updates retain ordered coverage. Obsolete (span ID,text revision) keys retire.
Other AST/body/calibration/event behavior is reverse-proved unchanged. Its
HOST11 and short Live47/Saved48 passes retain those exact scopes; hour05 failed.
Revision wall time includes lock/snapshot/association/publication, not model CPU.

Build33 writes the selected compact record after patch-first canonical sizing.
A one-shot C encoder still materializes a current JSON string; chunked UTF-8
hash/count avoids its whole byte copy and discarded full-wrapper allocation.
Immutable bytes enter the unchanged FIFO/guard/fsync path without a string
round-trip. HOST14 matched exact record bytes and logical digests. Traced
preparation peak 1,868,863 to 961,646 bytes and measured CPU cases improved; no
native sustained or leak conclusion follows.

The current35 worker retains finite 1 GiB AS before project/model reads. Inside
native_scope retains 256 MiB soft/1 GiB hard; independent metadata remains 128 MiB.
Shared parents select 1 GiB only for full_app_hour or the exact fresh
output/classic_driver.py Live/Saved RedimNet/TitaNet job. Other parent kinds
retain 768 MiB. Actual ENVELOPE/UNIT_OWNERSHIP reports getrlimit pairs. HOST10
checked source/order/policy/receipt contracts. Hour08 adds source completion with growing lag. Normal03 capture/Stop/Discard subpasses and separate idle Exit05 are proven; normal03 overall remains FAILED its observer.
Physical RAM/disk floors, CPU/stack/core/tasks, source ownership, backlog and
calibration controls are unchanged.

The gallery32 candidate removes inherited People/roster/reference totals,
snapshot 1024-file/16 MiB and export 32 MiB ceilings. Nested scandir walks and streamed
copies/exports retain small buffers, complete hashes/readback, root/destination
physical guards, consent, namespace and ordinary owned-file checks. HOST20
verified those contracts; large-gallery native performance is not measured.
## Shared34 source changes retained in current35

The immutable SQL metadata cache retains at most 8 MiB and returns fresh parsed
copies. HOST17 verified commit/fault/group invalidation and exact rows; its
200-read/20-unrelated-commit fixture opened one candidate read connection versus
200 in the reference. This is query-count evidence, not native throughput.

S7 HOST19 compared 186 valid mode/settings/ownership combinations and 40
successive revisions. Only discarded initial copies changed: segments-list calls 1→0
and accepted snapshot calls 2→1 in supported modes; final detached segment copies,
ordered outputs, raw words, source clocks, labels and conservative mode matched.
The actual merged Engine hook is hash-bound and instance-local before workers.

Prepared native output allocation uses reported count - base rows instead of a
source-duration-sized upfront buffer. It still copies the full retained C ABI
probabilities and protects new emitted rows from later writes. Admission counts
the old live workspace plus the new workspace/output/two validation masks, under
the current effective AS ceiling and actual 192 MiB physical RAM floor. Source/
final endpoint and 10 ms frame checks remain. The repeated-source hour completed; natural-input quality and sustainable real-time remain unqualified.

The current reviewed ordinary manual policy sets max_backlog_seconds=None and
storage-derived finite source/drain ceilings. Historical/timed defaults retain
120 seconds; optional refinement has its separate finite backlog admission.
Model loading and cleanup stay finite. No model, window geometry, thresholds,
acoustic work, evidence lifetime or identity calibration changes.


## Native token math and caption provenance

Original Sherpa rule3 forces a 20-second endpoint; the original loop resets and
publishes a final on any endpoint. The repair preserves that internal reset to
bound result history, but separates a recognition-piece final from a completed
spoken utterance. Immediate partials remain. A piece at least 20 source seconds
is conservatively recorded as resource; a shorter endpoint as native_pause.
The pinned API supplies only an endpoint boolean, so this does not assert which
native rule fired or establish acoustic causation for a reported cut word.

Engine(SegmentedAsrMixin, Parent) delegates the unchanged pinned ASR loop through
_SherpaSegments, reading actual BPE tokens before reset and accepted source
samples excluding finish padding. Source admission verifies runtime SHA256
64c8021099be59578f1408228bd4dda6b76821f9efd29b2f68172b3f0938f78c and model-wrapper
SHA256 d15972b6968ea8a1d5a8c76bba2fe30d504df5f0b1e7963a1166c65d4fcd9056.

Pinned greedy decoding emits at most one nonblank token per 40 ms frame:
20.3 / 0.04 = 507.5, approximately 508 subwords. Maximum retained vocabulary symbol
length 10 gives approximately 5,080 raw symbol characters per such piece, excluding
fixed context/model allocations and object overhead. This is source arithmetic,
not RSS measurement. Reset retains encoder state/last decoder context; consumed
features are discarded. A 100 ms read is 1,600 float32 samples = 6,400 bytes. Simply
disabling resets would still grow decoder token/text history without a bound.

A first actual BPE token with a word-start marker supplies a space after a
resource reset; without it, the joiner is empty. Fixtures join PARTICUL + AR
while preserving VERY VERY. No word deduplication or spelling heuristic is used.
Same-piece revisions replace the authoritative suffix; duplicate finals are
idempotent. Raw words/source intervals survive PnC and delayed identity updates.
Native token emissions and coarse ASR/ownership windows are **not phonetic word
timestamps**. Boundary/joiner/readiness fields come from the production facade.

Pause or Stop closes the spoken group. An empty silence piece may close the
preceding group without enlarging its original source interval. Disk-backed PnC
uses at most two 96-word/4,096-UTF8-byte windows; an unusually long lexical word
uses exact raw fallback rather than the native 200-BPE assertion. The guard
preserves lexical characters, decimals and abbreviations; changed words/counts
fall back to raw. Bounded context seams remain a native quality-review tradeoff.

## Source order, paragraphs and History

One transaction replaces an exact parent's current partition and retires absent
children while preserving revision evidence. Older source revisions cannot
resurrect children; equal conflicting versions reject; exact duplicates add no
event/charge. Producer display versions, durable presentation revisions and
the user's view counter are separate. A persisted native-parent source anchor
and span/token order prevent a later coarse zero-second fallback from preceding
an earlier aligned 1.1-second child. Actual child clocks remain unchanged.

Export10 structural baseline: 60.4 processed seconds, 48 indexed spans, 39 spans
from three latest revisions, nine obsolete spans; 177 indexed versus 168 current
word instances, with 26 current spans containing one to three words. Executed
projection gives **five paragraphs, all 168 current word/token positions and
verified native-parent token order**. Three paragraphs are explicitly unverified
unattributed groups. All labels remain Unknown; 37/39 top-level rows lack a
supported track ID. Adjacent unattributed text can share a presentation paragraph
without claiming a common biometric speaker. Known track transitions, source
gaps and explicit breaks remain boundaries. Historical saved evidence is not
erased/backfilled. These counts are not human readability or acoustic accuracy.

Live rendering retains a bounded tail; manual History pages retain a frozen
parent window/scroll anchor, with explicit Return to live. The retained renderer
revises text in place. Compact default is 19 px, with larger accessibility choices
and saved preferences preserved; pending styling is steady/muted. Read throttle
250 ms to 100 ms implies approximately 320 ms to 160 ms at ideal 80 ms UI ticks,
before query/scheduling work. These are calculations, not screen measurements.

## Capacity and temporary-session removal

Duration-derived SQLite/text quotas no longer reject accumulated valid data. Activated build35 also removes inherited gallery totals. Physical free space and byte/fraction
reserve still govern admission. Segmented files, bounded queues/payloads,
transaction batches and UI windows protect working sets without limiting total
history. Encoder namespaces/model validity/identity thresholds are unchanged.

SQLite includes main/journal/WAL/SHM extents; finite file allowance expands from
existing extent plus free bytes above reserve, capped by filesystem capacity
minus reserve. Linux raises only the soft limit within the inherited physical
hard ceiling. Owned regular single-link paths are required. Build30 handles a named regular
zero-link sidecar with one final non-following recheck: absent is no named extent;
a different ordinary nonzero single-link inode is charged max(old,new) size.
Main zero-link, symlink/reparse/nonregular/hardlink and uncertain observations
still reject. Double rapid turnover can reject conservatively; parent lstat is
not an atomic secure-open guarantee. Sidecars are not silently removed.

**Known cleanup edge:** before every writable LocalStore connection the planner
requires 2 * metadata_bytes + 8 MiB above reserve. At metadata 0, below reserve+ 8 MiB
even writable reads/deletion validation can fail before the first unlink. The
ASR ledger's 4 MiB planning input requires 16 MiB above reserve. Logical quota
removal therefore does not prove Discard always frees space near the physical
floor. This confirmed edge is unresolved in the frozen candidate.

Explicit Discard/Delete takes the selected session's exclusive lease, validates
ownership/artifacts and persists a store-bound intent before unlink. Media goes
before bounded index purges; owner metadata goes last. Startup resumes only
persisted explicit intents, not arbitrary orphans. Kept sessions require
deliberate Delete. Completion retains only a minimal non-content receipt.
Actual native recovery/retry/next-session ownership need separate evidence.

## Backend, Mode and calibration guide

Choose backend and Live/Saved input before the portrait app opens. All six
ordinary rows share Sherpa ASR/PnC. Backend selects diarization timing/encoder;
Mode selects continuity, identity and display policy.

| Ordinary backend combination | Personal naming gate |
| --- | --- |
| Pyannote + ReDimNet2-B2 FP32 | Original C088 resolver/gates retained; personal-domain accuracy remains unevaluated here. |
| Pyannote + TitaNet-Large FP32 | Exact TitaNet/query-domain/roster calibration required; currently blocked. |
| Nemotron CurrentDelayed + ReDimNet2-B2 FP32 | Exact delayed-query/ReDimNet/roster calibration required; currently blocked. |
| Nemotron CurrentDelayed + TitaNet-Large FP32 | Exact delayed-query/TitaNet/roster calibration required; currently blocked. |
| Nemotron Chunk52, two native threads + ReDimNet2-B2 FP32 | Exact Chunk52-query/ReDimNet/roster calibration required; currently blocked. |
| Nemotron Chunk52, two native threads + TitaNet-Large FP32 | Exact Chunk52-query/TitaNet/roster calibration required; currently blocked. |

Separate encoder galleries provide compatible references; enrollment does not
fit calibration or verify a name. Raw cosine is not a probability. C088 gates
never transfer to TitaNet/Nemotron. Other five rows can execute voice queries and
report rejection reasons without accepting biometric names. Calibration and
evaluation require independent sessions/participants and exact model, query
domain and roster provenance.

| Portrait Mode | Operator meaning |
| --- | --- |
| Just Transcription | All words, neutral label, no personal lookup. |
| All enrolled - one Unknown | Compare compatible references in the active encoder gallery; inadequate evidence stays Unknown. |
| Selected names - one Unknown | Match only the selected compatible roster; outsiders can remain Unknown. |
| Selected - closed group | Always display a selected name. Missing voice may use a source-linked current/recent assumption or first roster fallback; assumed names are unverified and cannot train identity. |
| Spatial - all enrolled / selected names | Actual C079 cues support voice association; missing cues fall back to voice. Directions do not verify names. |
| Strong spatial - all enrolled / selected | Retained C060 weighting with freshness/motion/conflict guards. Experimental; independent voice naming gate remains. |
| Seats - direction only | Fresh unique manually anchored seat supplies an explicit assumption; stale/ambiguous/moved cues cannot inherit its old name. |
| Seats - voice + direction | Calibrated voice plus retained seat/conflict policy. Apply at this location; re-anchor after Stop/movement. Calibration blocker remains visible. |
| All enrolled - numbered Unknowns | Named lookup plus numbered anonymous continuity; tracks can split/merge. Available through Advanced. |

The contract retains 12 Mode keys; the frozen portrait menu filters standalone
anonymous_conversation/Numbered Unknowns, leaving 11 keys across Mode/Advanced.
It is not a seventh ordinary backend. Matching roster and display roster are
separate; a display filter does not restrict matching or remove audio. Plain
saved WAV lacks beam/BMI; spatial replay needs a kept rich recording. Stop/drain
before changing processing Mode/gallery/backend. Settings' Return to backend
combinations closes the controller and returns idle to the chooser; Discard
itself does not trigger this transition.

## Maintained source/run references

This draft generates no code and has no executable inputs/outputs. Helpers load
through the versioned owned launcher. Purpose, inputs/outputs and exact
PowerShell/CMD/Anaconda commands remain in README_CORE_REPAIR.md,
README_ASR_SEGMENTS.md, README_CAPTION_REPAIR.md, README_STORAGE_RECOVERY.md,
README_RUNTIME_CAPACITY.md, README_IDENTITY_MODES.md and README_GALLERY_CAPACITY.md.
Use their owner/source/closure protocol. Update this draft with actual native
results before using it for operator handoff; it does not replace current guides.


Hour08 completed57.6M samples with one model/diarizer setup and8398 indexed parts. D1 revisions20811calls/321.313s wall; diarizer pushes1615.660s plus6.499s finish include nested embedding work. These overlapping times are not additive compute RTF. Startup first-text0.893s/first-speaker0.944s does not describe later latency; backlog grew to495.360s.

Mirror871files/1,336,004,013B/1729 compact segments: native segment SHA and PC segment/file SHA, source identity/membership before-after checked. Native source whole-file SHA was not established; empty directories were not copied. Quality/natural conversation/GUI endurance remains unqualified.
