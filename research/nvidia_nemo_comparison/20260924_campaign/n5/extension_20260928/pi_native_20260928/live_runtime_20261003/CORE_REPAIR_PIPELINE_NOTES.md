# Six pipeline technical notes

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

Use the six-row chooser to select Pyannote, CurrentDelayed or Chunk52/two native
threads, each with ReDimNet or TitaNet. Live/Saved input and Mode are independent
choices. Open Application is idle; Start authorizes capture. Unknown, closed
display assumptions and calibrated biometric identity are separate outcomes.

The final source is linked by
[current_build35/SOURCE_MAP](core_repair_20261006/current_build35/SOURCE_MAP.md).
[Technical notes](CORE_REPAIR_TECHNICAL_NOTES.md) explain shared source-token,
paragraph, capacity and resource contracts. Original per-pipeline math below
retains its exact encoder/query domain; historical RTFs are not successor passes.

Build35 inherits the tested gallery32 capacity repair and shared writer33
allocation repair. Writer HOST14 matched exact compact bytes/digests and reduced
traced preparation peak 1,868,863 to 961,646 bytes. AS HOST10 checked the finite
source-bound1GiB worker/admitted recording-parent policy and unchanged physical
guards. Neither measurement qualifies native throughput or an encoder ranking.

## Shared production path and evidence

All six rows compose Engine(SegmentedAsrMixin, Parent). The facade verifies
original runtime/model-wrapper source pins, delegates the original native ASR
loop and observes actual accepted samples/BPE tokens before reset. The original
20-second resource reset remains; recognition-piece finality differs from
spoken-group closure at pause/Stop. A real first token word-start marker gives
a space; absence gives an empty continuation joiner. Genuine repeats remain,
same-piece suffix revisions replace, and duplicate finals are idempotent.
No global dedupe, spelling rewrite or phonetic timestamps are introduced.

One nonblank token per 40 ms frame implies approximately 508 tokens at 20.3 s.
The maximum vocabulary symbol length 10 implies approximately 5,080 raw symbol
characters, excluding fixed native/model state/object overhead. This is source
arithmetic, not measured RAM. Audio reads are 100 ms / 1,600 float32 samples /
6,400 bytes. Blindly removing resets would grow decoder result history.

Spoken groups are disk-backed; PnC uses at most two 96-word/4,096-UTF8-byte windows
and exact lexical guards/raw fallback. The ledger's actual physical admission
uses 4 MiB planning metadata, requiring 16 MiB above the configured reserve.
It does not load whole-session audio/text into RAM. Bounded context seams need
native quality review. Raw words, exact source intervals and actual boundary/
readiness/joiner fields reach InstalledSession._caption before atomic projection.

Storage orders by stable outer-parent source anchor and child/span order.
Coarse child-clock fallbacks cannot reorder native token ranges. Delayed labels
use separate durable presentation revisions; older source projections cannot
resurrect retired children. Unknown/null-track text can share an explicitly
unattributed paragraph with no shared-speaker claim. Token emissions/activity
windows are not phonetic alignment. History/manual-scroll windows are bounded.

Logical duration-derived metadata quotas are removed; the33 candidate also removes inherited gallery totals, with consent, namespace and physical guards retained. Real filesystem
reserve, finite file ceiling, queues/payloads/transactions and model ownership
remain. The unresolved reserve+8 MiB writable-SQLite edge can block cleanup
before its first unlink; no per-pipeline note overrides that physical guard.

## Pyannote + ReDimNet - pyannote_redimnet

Build29 Saved35 is independently finalized PASS over the full matched 60.4 s
source: 71 nonempty stored parts, complete new-output Discard and closed mirror.
This result does not establish caption/speaker accuracy or a successor pass.

Retained Pyannote segmentation/powerset activity feeds continuity and ReDimNet2-B2
FP32 normalized voice evidence in its own namespace. The original C088 resolver
and gates remain; the repair does not establish personal-domain accuracy.
Selected closed supplies visibly unverified source-linked assumptions when
voice is unavailable; they cannot become enrollment/adaptation evidence.
Generic C079/C060 spatial policies retain cue freshness/motion/conflict guards.
Rich saved replay uses original source beams/BMI, never current sensors.

Historical build26 CHECK21's 60.4 s speech/Save and CHECK28 rich replay keep their
actual scope. Export10's 39 current spans/ 168 word instances structurally become
five paragraphs, three explicitly unattributed, without word loss. This does
not qualify acoustic reset quality, native build29 or human readability.

## Pyannote + TitaNet - pyannote_titanet

Build29 Saved36 is independently finalized PASS over the same full source:
18 nonempty stored parts and closed mirror. COMPLETE does not mark a complete
session Discard passed. TitaNet calibration/accuracy remains separate.

Retained Pyannote activity is paired with the exact TitaNet-Large FP32 frontend/
encoder and separate gallery. No ReDimNet vectors/thresholds are converted.
Voice queries may run, but biometric naming requires independent TitaNet-query
domain/roster calibration; the blocker is explicit. Closed group/direction-seat
names are assumptions; hybrid seats still require accepted calibrated voice.
The shared caption/source ordering/PnC path does not establish encoder accuracy.
Historical saved pipeline/quiet live checks retain their distinct evidence.

## CurrentDelayed + ReDimNet - delayed_redimnet

Saved43 recorded diarizer (push + finish) / 60.4 s RTF 0.384 and paced
source-origin through consumer completion 88.2 s. The latter includes waits/drain,
not compute RTF or a whole-app sustained result.

Build30 Saved43 now has independent functional PASS/full closed mirror on the
matched 60.4 s source, 137 nonempty stored parts, 117 embedding invocations and
complete Discard. This bounded success does not prove the historical37 suffix/
inode/link cause or personal-domain naming/continuous-speech quality.

Build29 Saved37 whole GUI/store check FAILED its SQLite single-link guard.
The worker reports successful cleanup. The historical offending suffix is
unproven; a storage-only successor requires separate package/native receipts.

Geometry remains cache264/FIFO0/chunk264/right1/left1/update188, 80 ms frames:
nominal 21.20 s buffering excludes compute/association/queue delay. Shared ASR
partials remain independent of delayed speaker availability. Actual singleton
activity windows supply source-clock cue association; mixed/overlap is not a
majority-speaker shortcut. Late-label policy preserves source intervals and
reprojects the same caption parent with a new presentation version.
ReDimNet namespace alone does not transfer C088 calibration to delayed native
queries; exact domain/roster calibration is required for biometric naming.

## CurrentDelayed + TitaNet - delayed_titanet

Build30 Saved44 independently finalized PASS/full mirror and complete Discard.
Recorded diarizer RTF 0.379; paced source-origin to completion 101.0 s includes
waits/drain. The full same source supplied 137 stored parts/117 embedding calls,
without naming/calibration or sustained qualification.

The same delayed native geometry/timing feeds exact TitaNet voice queries.
Both encoder and native-query domain differ from the original C088 gate;
independent compatible calibration is required. Display assumptions can work
without calibrated names, and missing/stale cues fall back to voice association
rather than inventing directions. Historical CurrentDelayed/ReDimNet latency
or RAM is not a measurement of this encoder's complete build29 pipeline.

## Chunk52/two threads + ReDimNet - chunk52_2t_redimnet

Build30 Saved45 independently finalized PASS/full mirror and complete Discard.
Recorded diarizer RTF 0.991; paced source-origin to completion 135.0 s includes
waits/drain. This short observation does not establish whole-app real time or
hour behavior; full same source/137 parts/117 embedding calls retain their scope.

Geometry remains cache264/FIFO80/chunk52/right1/left0/update40:
nominal 4.24 s buffering excludes compute. The exact separately pinned variant
requests two native graph threads; BLAS/OS settings and shared CPU quota remain.
Singleton/cue/late-caption policy is shared with the other native rows.
ReDimNet naming needs exact Chunk52-query-domain/roster calibration.
The preserved component-hour RTF 0.88445/late about 0.94/ 85.35 C peak is not a
whole-application hour or build29 thermal/quality pass.

## Chunk52/two threads + TitaNet - chunk52_2t_titanet

Build30 Saved46 independently finalized PASS/full mirror and complete Discard.
Recorded diarizer RTF 0.805; paced source-origin to completion 117.5 s includes
waits/drain. Separate short observations do not establish an encoder speed ranking
or personal-domain naming; full same source/137 parts/117 calls retain their scope.

The same exact two-thread variant uses TitaNet's separate frontend/gallery.
Its encoder/query-domain/roster calibration blocker remains independent.
Component performance cannot substitute for TitaNet model loading, eligible
clean voice accumulation, actual query/raw-cosine decisions or sustained GUI
behavior. Raw cosine is not a probability; participant enrollment is not
calibration. All shared source/paragraph/storage safeguards remain.

