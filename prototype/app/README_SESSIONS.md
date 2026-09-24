# Linked developer conversations

Task 03 adds a private archive beside the existing rotating diagnostic logs.
`sessions.py` stores/indexes evidence; `session_controller.py` uses the single
existing capture/model owner; `session_playback.py` owns only an explicitly
selected playback output; `session_ui.py` supplies touch pages. No new model,
library, USB owner, microphone stream or inference algorithm is introduced.

## Run and use

From the repository in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

From CMD or Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

On the provisioned CM5 release use the existing `python main.py` launcher with
that release's environment/data/model paths. ARM64 hardware verification is
still pending. Windows evidence does not qualify CM5 memory/performance.

1. Settings → Developer Sessions → New transcript (text only), or New transcript
   + exact audio after obtaining participant consent. Neither starts a microphone.
2. Press Start on the main screen. An audio session shows **● SAVING EXACT AUDIO**.
   Ordinary Start creates a text-only draft automatically when required.
3. Stop drains the same capture and inference path. Save pins the conversation.
   New preserves the previous draft. Stop/Start and mode changes create distinct
   epochs within the current draft; saved conversations are never appended to.
   Models remain cached across epochs. Starting after opening an old conversation
   creates a new text-only draft instead of recording into historical evidence.
4. Open a library conversation and choose Reopen to load its captions and coarse
   audio interval buttons. Choose/refresh an explicit listening output first.
   Playback stops and releases capture before opening output; enrollment blocks
   playback. Start/enrollment stop playback first. No default output is selected
   or changed, and unsupported endpoints fail visibly without fallback.
5. Rename, note, separate user correction, Save/pin, export, and confirmed Delete
   are available on the conversation page. Deleting a conversation never deletes
   people, enrollments or reference recordings. Text export omits audio, roster
   IDs and identity vectors; full export includes sensitive native evidence.

Inputs: the existing live or explicitly prepared file source, current settings,
models, roster and native events. Outputs live under
`<resolved JUST_PEACHY_DATA>/conversations`; the default on this desktop is
`C:\Users\amiri\JustPeachy\data\conversations`. Exports default to sibling
`conversation_exports`. These are local **unencrypted** speech/text/identity
data, with no upload. Audio consent applies to one logical conversation only.
Old diagnostic logs are not retrospectively given missing audio or migrated.

## Exact source and metadata

Each UUID conversation has `conversation.json` and `epochs/<uuid>/` containing:

| File | Meaning |
|---|---|
| `epoch.json` | State, mode/recipe/tap/roster, effective profile, code/model hashes, clock descriptions, source/capture integrity, byte/sample counts, archive loss and master hash |
| `model_input.f32le` | Optional headerless little-endian float32 mono, 16,000 Hz; exact admitted model input, including noise/silence |
| `events.jsonl` | Immutable native raw/revision/name/gap events plus separate `prototype_formatted_text` records; original wall clock and receipt monotonic clock remain distinct |
| `windows.jsonl` | Actual embedding/segmentation event references, half-open sample indices, padding, shape and availability clocks |
| `resources.jsonl` | Approximately 1 Hz process CPU seconds/core-relative percentage, RSS, writer and pipeline queues, source cursor, clock origin and configured features |
| `captions.sqlite` | Rebuildable offsets into immutable event/format records; no duplicate transcript/audio archive |

The current ASR and identity path share one float32 mono journal. Live O0's
existing gain occurs once upstream; O1 retains unity. Prepared O0 WAV data is
already prepared and is not gained again. The pipeline's declared additional
gain is 1.0. This archive is post-XVF model input, **not raw microphones or all
focused beams**. Segmentation windows reproduce the declared left-zero padding;
embedding windows are source slices. Normalized output embeddings are not an
audio normalization transform. Export windows on demand from a pinned source
using `../tools/export_session_window.py`; see its README for commands.

Float32 costs 219.73 MiB/hour (16k × 4 bytes); PCM16 would cost 109.86 MiB/hour.
No PCM16 copy is labelled exact. The master can be read with
`numpy.fromfile(path, dtype='<f4')`; sample k is at byte 4k. `.npy` window exports
include a JSON transform/hash sidecar. The archive uses existing NumPy/psutil/
sounddevice and Python's standard-library SQLite; no dependency was installed.

Caption audio intervals are coarse utterance spans, not word alignment. Raw ASR,
provisional casing, final punctuation and explicit manual corrections are
separate. Reopening uses indexed stored formatting. The active GUI mode still
controls how reopened names are presented; original mode, native identity/name
events and UUIDs remain in the evidence. Annotations record explicit user
provenance. Host receipt time, source samples, ADC metadata, modeled availability
and observed/publication clocks are not collapsed into acoustic arrival times.
CPU values are process measurements, not watts; no estimated SNR is recorded.

## Bounds, retention and failure policy

- Linked archive target: 2 GiB total including existing conversation files at
  epoch admission; 2 GiB disk free floor. Payload caps per epoch: 256 MiB audio
  (about 69.9 minutes) and 64 MiB metadata. SQLite/manifests add bounded-per-epoch
  overhead to payload admission, so this is a target, not a byte-exact filesystem
  reservation. Existing diagnostic/profile storage is accounted separately.
- At new-draft/epoch admission, oldest inactive unpinned drafts are removed as
  needed for the quota/10-draft policy. **Save pins against automatic deletion.**
  If pinned data fills the target, new archival fails visibly; nothing pinned is
  silently deleted. Explicit Delete can remove saved data after confirmation.
- The side writer is bounded to 512 items / 4 MiB pending bytes; individual
  records are limited to 128 KiB. Audio copying/encoding, inference, disk and
  resource sampling happen outside PortAudio's callback. Records are source
  indexed, not buffered in an unlimited transcript list.
- A full queue, disk/full quota or failed write stops that epoch's archive and
  exposes `PARTIAL` plus the loss receipt. It never pads gaps or silently resumes.
  The independent live journal/captions can continue. Existing native pipeline
  storage/hardware failures can still stop the pipeline when continuation is
  infeasible. RAM status remains visible if even final metadata cannot be saved.
- Atomic metadata/checkpoints, periodic/final fsync and rebuildable SQLite indexes
  support process-interruption recovery. Startup marks unfinished epochs
  `RECOVERED_PARTIAL`; complete float samples are usable, torn trailing bytes and
  unknown tail loss are preserved/reported. This is not a power-loss guarantee.
- UI holds the latest 512 caption rows, latest 100 conversation summaries and
  latest 20 annotations; exports stream every indexed caption. Notes/corrections
  are capped at 200 each. Each playback/window action is at most 60 seconds.
  Completed conversation size/free-space summaries refresh on session actions;
  current writer counters remain available in live snapshots/resources.
- Output must support explicit 16k mono float32 playback; endpoint changes and
  underflow are reported. No resampling/volume/default-device fallback is hidden.

See `../docs/UIITER2_03_HANDOFF.md` for exact checks, limitations and rollback.

Task10 optional enhancement: `model_input.f32le` retains original post-XVF input; `enhanced.f32le` and transforms identify the optional output/fallback. ASR/identity stream selections are explicit in each epoch. Both count toward audio quotas and require consent. Reopen controls can listen to either; exported model windows use their recorded stream. See README_NOISE.md.
