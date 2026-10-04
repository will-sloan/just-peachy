# Pyannote primary with optional delayed D1 correction

Status: concrete integration design, not an enabled native mode. Whole-pipeline
RAM/CPU admission is pending. The default primary engine, frozen packages and
root integration were not changed for this design. The existing single-D1 late
labels option does not fulfill a two-diarizer provisional/correction requirement.

Purpose: show text and genuine provisional speaker evidence from the current
Pyannote/embedding path immediately, then revise historical speaker attribution
on the same caption/token IDs using one delayed D1 context when resources permit.
Unknown is the primary fallback where the current tracker has no supported
identity. Direction alone must not manufacture a name.

## Smallest useful model composition

Keep one existing Sherpa ASR, Pyannote segmentation/tracker and selected
ReDimNet/TitaNet embedding instance in the primary process. Add one anonymous
CurrentDelayed D1-only child process with its retained LRU1 library. Do not create
a second full `N2ResidentModels` bundle: it would also acquire another ASR stream
and optional embedding models. The native D1 binding alone is sufficient for
the refiner. No new model export, weights or altered thresholds are needed.

The child reads the same committed, once-gained 16 kHz processed source as the
primary from a bounded read-only view of the session journal. It consumes every
sample in order, in bounded blocks, with one model construction and one final
flush. No artificial concatenation of disjoint uncertain windows, stream reset,
silence removal or skipped gaps. IPC carries committed sample watermarks and
bounded result references; audio need not be duplicated into an hour-long RAM
buffer. A safe cross-process read-only journal view still needs implementation;
do not assume the existing writer/SQLite object can simply be shared.

A separate child permits terminating only a failed optional native call while
primary text continues. It costs another Python/native workspace, so it must be
measured as part of the same admitted CPU2/3, aggregate200% group. Two separate
200% units are not an acceptable interpretation of that shared limit. Starting
another thread in the primary is simpler, but a hung native call cannot then be
stopped independently without taking down the primary.

## Existing, inspected integration points

Installed source root:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12`.

* `app/pipeline.py:ResidentModels.acquire` retains the current recognizer and
  speaker models. `PrototypeEngine` uses the common installed `PipelineEngine`.
* `vendor/edge_speech_pipeline/runtime.py:_speaker_loop_v2` publishes real
  segmentation/embedding source spans and persistent tracker decisions.
  Pyannote local channels are explicitly per-invocation and must never be
  treated as persistent speaker IDs. Use accepted tracker/history IDs instead.
* `app/n2_pipeline.py:ActivityTimeline` consumes actual D1 frame origins, clips
  final overhang to real audio, uses the retained threshold0.5 and abstains for
  mixed/overlap coarse windows. Reuse these semantics without hidden tuning.
* `app/n2_pipeline.py:_revise_supported_spans` demonstrates the genuine
  `transcript_label_revision` payload: exact `target_text_revision_id`, explicit
  `target_span_ids`, source evidence interval, current caption target interval,
  version and evidence IDs. It never changes raw words.
* `vendor/edge_speech_pipeline/research_n1_spans.py:apply_identity` rejects stale
  target revisions/IDs/disjoint evidence and appends speaker history while
  preserving the caption's token IDs and raw text. This is the suitable existing
  presentation path for accepted correction events.
* `installed_engine.py:_caption` persists the existing caption key with UPSERT.
  That path can consume revised presentation rows without duplicate captions.

## Proposed data flow and correction authority

1. Primary ASR and speaker work continue unchanged. The UI receives every normal
   text event immediately. Supported Pyannote/tracker labels may be shown as
   provisional; unsupported labels remain Unknown. The correction worker is
   never awaited from text production, capture or the primary event consumer.
2. Record bounded primary anchors from supported historical identity intervals,
   retaining the real persistent tracker ID, identity evidence IDs and exact
   source sample interval. Do not convert ASR observation windows into phonetic
   word boundaries. Keep only anchors needed for the admitted revision window.
3. D1 emits only actual completed frames. Convert exclusive activity runs to
   exact sample intervals on that same source clock. Preserve overlap/unknown
   cases; do not select a majority speaker for a mixed coarse caption window.
4. Use independent-speaker permutation alignment over the same-source overlap.
   Map D1 slots to persistent primary tracks using supported intervals, not slot
   numbers or display names. Ambiguous/unmapped slots abstain. Named labels may
   come only from the already-supported primary identity evidence; D1 itself
   adds no gallery match. This conservative mapping can repair local assignment
   errors, but cannot invent a newly identified person or guarantee quality.
5. The primary consumer polls a bounded result queue without blocking. For each
   still-current span, emit the existing historical `transcript_label_revision`
   payload with explicit target IDs/version and an additional mapping/source
   provenance digest. Re-read the current caption revision before publishing;
   discard stale results. Unchanged signatures emit nothing. Text, token IDs,
   caption keys and original first-shown speaker history stay intact.
6. Expired, ambiguous or failed refinement keeps the last valid primary label
   and displays an explicit fallback/refinement-unavailable state. It does not
   block or retract text. Correction cannot grant live voice/direction authority.

The current `CaptionLedger` has useful permutation/interval/expiry primitives,
but its immutable text rows are not a direct replacement for the installed
streaming ASR presentation. Applying its full caption event could replay stale
partial text. The bridge must use only speaker/evidence patches against the
current S7 span revision. The current `RefinementCoordinator` schedules independent
window jobs; a continuous D1 cursor is a different worker contract. It must not
be wired as if those windows were independent inference sessions.

## Latency and resource policy

CurrentDelayed has about21.3 seconds of required source buffering before its
first regular result, plus compute and scheduling time. The existing30-second
revision window may be too short under contention. An explicit experimental
60-second revision window is a candidate to measure; do not silently change the
normal default or promise a correction deadline before measurement.

Retain the primary source-duration policy, default300 seconds and explicitly
admitted developer sessions of at least3600 seconds. Refiner deadlines and drain
budgets are separate from capture duration. Use a small bounded result queue,
one pending watermark rather than duplicated audio jobs, and a finite source
lag limit no larger than the useful revision window. If the optional worker
cannot catch up, stop/degrade it explicitly for that session. Do not drop a gap
and continue labeling its state as a continuous stream. Primary source loss,
primary backlog overflow or storage failure remains an actual session failure.

The child must have a verified owner, model/library/source pins, finite process
limits and a private bounded output allocation. Stop/EOF must close it or retain
failed ownership explicitly. A killed/expired optional worker cannot be reported
as a successful refinement pass. The primary can finish independently while the
supervisor performs finite optional-worker cleanup.

Whole-pipeline admission must cover primary plus refiner: first text, first
supported provisional label, correction availability/coverage, CPU contention,
rolling RTF/backlogs, drops, memory PSS/RSS/virtual/available/swap, output bounds,
and actual closure. D1-only component memory does not admit this composition.
The one-thread CurrentDelayed baseline is the initial candidate; the separate
two-thread Chunk52 experiment must not be assumed to leave primary CPU headroom.
No 4/8 GB native performance estimate substitutes for current2 GB measurements.

## Required new integration, after admission work

Use a distinct explicit mode and matching admission schema for Pyannote primary
plus D1 refinement. `RuntimeSelection` currently rejects Pyannote with provisional
correction, and `validate_native_admission` assumes a fast Nemotron profile. Those
are real missing routes, not flags to bypass. A revised schema must identify
both actual model profiles, embedding/gallery space, input source, primary and
refiner resource budgets, observed measurements and exact receipt pins.

The implementation work is: bounded read-only journal adapter; supervised
persistent D1-only child; provenance-preserving primary-anchor collector;
nonblocking result-to-S7-span revision bridge; optional-worker degradation and
closure; explicit selector/status only when its measured admission exists.
Synthetic permutation/expiry/no-duplicate tests can validate contracts, but
cannot create that native admission. Neither the worker nor this mode is enabled
by this design document.

Inputs for future qualification: one pinned matched source, existing compatible
named gallery if used, pinned baseline/refiner descriptors and explicit finite
policy. Outputs: original immediate caption events, same-key speaker revisions,
mapping/source provenance, degraded-state counters, complete native resource and
closure receipts. No runnable command is supplied because the native mode is
not implemented; existing PowerShell/CMD/Anaconda commands remain documented in
[README_PIPELINES](README_PIPELINES.md) and [README_NATIVE_BENCHMARK](README_NATIVE_BENCHMARK.md).
