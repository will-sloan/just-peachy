# Native memory and retained-history audit

This is a read-only source audit, not a native test or a 60-minute qualification.
No model, microphone, Pi command, or native library was run for this audit.

## Source identity

The installed application mirror is:

`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12`

Its `RELEASE_MANIFEST.json` was independently hashed as
`274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0`.
This matches v28 and the installed-release reference decoded from
`B/imu-integration-20261002/runtime-capsule-v3/COMMON_BUNDLE.json`, where
`B` is the campaign's `local/n5/research-extension-20260928/pi-native-20260928`.
References below to `app/` and `vendor/` are relative to that application mirror.

The native source inspected is:

`G:/Just_Peachy_N1/20260924_campaign/local/assets/source/NeMo-Speech.cpp-97a15afa5caa9bce5baaa86c1184103877af4101/src/asr/diar/diar_pipeline.cpp`

Its independently checked SHA256 is
`343b04ea976d3a8a108bf4d0ffc3210c0bb764e7b31725609d58ab1fe2da2cbe`,
matching the `scheduler-native-v1/inputs/source/src/asr/diar/diar_pipeline.cpp`
pin in `P/D1_ENDPOINT_CONTRACT_V3.json`. This establishes identity for the
timeline source; it does not claim that unexamined build inputs are identical.

## Native retained state

- `DiarStream` construction in `diar_pipeline.cpp:86` sets the probability
  compaction trigger to 20 minutes and retained tail to 10 minutes.
- `DiarStream::maybe_compact` at line 411 scans for an all-speaker-silent
  interval exceeding the segmentation postprocessor's temporal reach. If no
  qualifying cut exists, it returns without discarding probabilities. Thus
  the time constants are conditional compaction thresholds, not an
  unconditional maximum allocation.
- On a successful cut, `probs_` is shortened and its global `probs_base_`
  advances, but segments from the prefix are appended to `frozen_segs_`.
  This accumulated segment history has no count bound in this source.
- `DiarStream::run_one_chunk` trims consumed waveform and mel buffers after
  each committed chunk. AOSC FIFO/speaker history in `aosc_state.cpp` is
  compressed according to the selected geometry. These buffers are distinct
  from the probability and frozen-segment timelines.
- `vendor/edge_speech_pipeline/nemotron_diarization.py:230`,
  `NemotronDiarizer._update`, allocates `count - base` rows and asks the C API
  to copy all retained probabilities, then copies the newly delivered suffix.
  With no native compaction, the allocation and copy grow with duration.
  At 60 minutes, 100 frames/second by 8 float32 probabilities is approximately
  11.52 MB, excluding vector capacity, temporary copies, models and segments.
- The retained catalogue selects executable graph LRU1 for delayed and LRU8
  for streaming/chunk52. Those are different caches and do not bound the
  probability or frozen-segment histories.

No native compaction rewrite, periodic model reset, silence removal, or
speaker-state modification is proposed here. Those changes could alter
output semantics and require their own source and behavioral evidence.

## Application history and persistence constraints

- `app/buffers.py`, `MemoryJournal`, is a 120-second float32 ring. It rejects
  an older reader explicitly; it is not a complete-session audio store.
- `app/n2_pipeline.py`, `ActivityTimeline`, retains 120 seconds of activity.
  Name support is limited to 256 entries per slot. Association/signature
  dictionaries and run sets have pruning thresholds; these should not be
  confused with an archive of all historical identity evidence.
- `app/controller.py:227`, `Controller._consume`, and the S7 presentation
  retain at most 512 caption rows. A diarizer that trails far behind ASR can
  lose the ability to revise retired rows even when audio remains on disk.
- `app/app_bounded_artifacts_v1.py`, `compact_rows`, reads and reconstructs
  every caption and formatted row before applying its requested result
  limit. It rejects more than 2048 `(kind, key)` entries or more than 8 MiB
  of reconstructed payload. Requesting only 512 rows does not avoid this
  working-set gate.
- `app/sessions.py`, `EpochArchive`, defaults to a 256 MiB audio allocation.
  Its accounting includes float32 model input plus a PCM16 listening copy.
  One hour at 16 kHz mono therefore requires about 329.6 MiB before metadata;
  raw multichannel recording and enhancement add separate costs.
- `P/field_artifact_limits_v1.py` rejects PCM limits beyond 2,080,000 samples
  (130 seconds) and individual native/conversation journals beyond 16 MiB.
  Changing a manager duration alone cannot extend the archive.

## Active adapter constraints

The mounted `COMMON_BUNDLE.json` contains newer derivatives than some plain
files under `P`. In particular its `field_live_d1_v1.bind(..., mode=...)`
supports delayed, streaming and chunk52, including exact C-ABI geometry and
selected-library checks. The plain `P/field_live_d1_v1.py` is delayed-only.

The embedded source adapter `isolated_pipeline_source_v11._accept` stops at
1,920,000 samples and rejects more than 2,080,000. The raw source sink and
checked native diarizer also enforce the latter ceiling. Its `_finish`
validates physical stream closure, lease release and exact source/journal
coverage. The mounted receiver and spatial-motion mapping operate on source
timestamps. These closure and timing behaviors remain requirements of any
new adapter.

The retained v28 runtime's 300-second child lifetime is not a 300-second recording
allowance: its recording limit is 120 seconds. The retained component RTFs
are about 0.405 delayed, 3.634 streaming and 1.085 chunk52. They are not
integrated live-performance guarantees, and they show why capture duration
and subsequent processing/drain time need separate accounting.

## Scope of the disk journal

`audio_journal.py` addresses only retention and reading of admitted processed
audio using bounded Python working memory and an explicit session policy.
It does not fix native probability/segment accumulation, extend the old
artifact schema, provide persistent caption revision, or establish a native
memory/performance qualification. Those limitations remain visible rather
than being hidden by the availability of a disk spool.

## Retained presentation and terminal history (post07 review)

Pinned BASE `app/pipeline.py` constructs `timestamped_spans_v3` with `S6DSettings(max_display_rows=512)`. In `vendor/edge_speech_pipeline/research_s7_presentation.py`, `project` emits one current row; `full_view` changes its visibility, not an all-session transcript aggregate. `_consume` bounds retained rows and pending keys at512, with32 pending corrections per key; `_columns` caps2. `snapshot_rows` can copy the bounded512-row view for an N2 revision. `research_s6d.PresentationState` bounds its token mapping by the same512 rows.

`research_n1_spans.update_tokens` replaces the latest retired-span delta, rather than appending every retired span forever. Per-word speaker history keeps32 entries. Accepted raw text, token IDs and ownership/word spans can duplicate the current utterance's representation. The pinned ASR configuration enables endpoint detection with rule3=20seconds; runtime endpoint handling resets the stream and advances the utterance index. There is no independent byte/token ceiling before one display payload is constructed. A pathological dense20-second utterance can still reach the explicit1MiB logical-record refusal. No semantic row-history rewrite was justified by this evidence.

The scheduler is a separate growing-but-finite retained history: `research_scheduler.CausalScheduler` keeps at most4096 utterance records,1,000,000 admitted event IDs (IDs<=128characters),20,000 pending events and4 revisions per utterance. V3 decisions, segmentation and scheduling histories cap4096. Observed-clock metadata is pruned every128commands with pending/evidence/recent preservation; observed utterance history caps4096. These bounds do not establish acceptable RAM use for an actual full-application hour.

The concrete terminal-copy issue is `CausalScheduler.snapshot`: `deepcopy(list(self._utterances.values()))`. `runtime._watch_session` stores this snapshot in telemetry and emits it; `_write_revised_transcript` takes another full snapshot, and the summary serializes telemetry again. Thus a long session could cross1MiB in its terminal event despite bounded individual display rows. Post07 `final_snapshot.py` externalizes final rows after exact worker/scheduler closure, using untouched shallow shadow objects for original metadata and one copied/annotated row at a time. It preserves original fields/order with count/hash/segment receipts. The original4096-row mapping remains retained; only extra full-history copies and giant terminal serialization are removed. Host tests compare the actual retained snapshot and summary methods and verify the original snapshot sees zero shadow rows, never the4096 original rows.

The normal saved source reads one file to EOF, even when a longer developer policy permits it. Post07 `developer_replay.py` therefore requires explicit matching >=3600-second developer repetition, keeps one epoch/journal/model lifecycle, and records original input SHA plus each exact repeat boundary. Native full-application performance, thermal/time-bin trends and whole-unit RAM remain unqualified until the separately admitted job actually completes and all outputs are copied.
