# Core repair technical notes - draft, 2026-10-06

This technical reference records the candidate build28 derivative's implemented
contracts, host evidence and remaining limits. It is **not acceptance, activated
deployment, a native pass or final handoff**. Frozen replacement inputs and
current global guides are unchanged. No new backend/model/cloud speech service
or transcript rewriting is introduced.

## Evidence boundary

| Completed host check | What it establishes |
| --- | --- |
| Storage: 23 passed | Atomic partitions, parent ordering/paging, legacy read-only preservation, explicit deletion fault injection, finite-file and ASR-ledger admission. Synthetic stores; no real native database recovery. |
| Caption/ASR: 36 passed, 17 + 19 | Paragraph/history fixtures, actual production facade/ledger/PnC path using synthetic inputs, exact source-pin admission and Export10 structural comparison. No acoustic inference or physical GUI measurement. |
| Identity: 28 passed, 24 + 4 | Identity/cue contracts, gallery/capacity fixtures and actual pinned policy math. No native speaker accuracy or calibration. |
| Caption handoff: 5 passed | Narrow actual installed caption-method fixtures after the outer-parent source-anchor change; a separate rerun, not five native configurations. |

Registered CPU14 runs retained source backups/independent restores/readback,
closed temporary fixtures and naturally returned zero. Exact Windows owners
were independently verified absent. Evidence labels under local live-runtime
audit-preparation are storage c0710b73f88e43a2914d89965ea1405c, caption d4f512bf,
identity-contracts a00bee7bd3784ea4981d549c13a1535d, identity-pinned
01cd043e3a8242b2897f05d78d031499, and caption-anchor
51cffed76b5e4ce0942b8ad056f4d5c7; full paths are in the maintained READMEs.

**Pending:** native token compatibility, actual model/gallery loading and voice
queries, live/saved six-row integration, real Discard/relaunch, portrait/manual
scroll and physical display latency, independent speaker evaluation/calibration,
and sustained operation. Host fixtures do not substitute for these results.

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

Duration-derived SQLite/text quotas and aggregate gallery count/byte refusals
no longer reject accumulated valid data. Physical free space and byte/fraction
reserve still govern admission. Segmented files, bounded queues/payloads,
transaction batches and UI windows protect working sets without limiting total
history. Encoder namespaces/model validity/identity thresholds are unchanged.

SQLite includes main/journal/WAL/SHM extents; finite file allowance expands from
existing extent plus free bytes above reserve, capped by filesystem capacity
minus reserve. Linux raises only the soft limit within the inherited physical
hard ceiling. Owned regular single-link paths are required; sidecars are not
silently removed.

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