# Architecture and Extension Contracts

## Runtime flow

```text
Microphone callback / paced WAV producer
                  │
                  ▼
       fast normalize + resample
                  │
                  ▼
  append-only PCM16 source-clock journal
           │                  │
           ▼                  ▼
 native Sherpa lane     ONNX speaker lane
 ASR + final punctuation segmentation + ReDim
           │                  │
           └────────┬─────────┘
                    ▼
          timestamped event bus
             │             │
             ▼             ▼
         CLI / JSONL     Tk GUI
```

The journal is the only audio fan-out point. Consumers own independent sample cursors. Model objects never run on the microphone callback or GUI thread.

## Thread ownership

- PortAudio callback: copy native input blocks into the raw reserve only.
- Audio normalization thread: resample and append to the journal.
- ASR thread: read fixed 100 ms source blocks and own one Sherpa stream.
- The same ASR thread runs the INT8 punctuation graph once per finalized utterance; it never touches capture or partial decoding.
- Speaker thread: read fixed 250 ms hops, own online clustering, and call the persistent ONNX sessions.
- GUI thread: render immutable events and invoke backend operations.
- Enrollment callback/writer: copy input into a safety reserve and stream PCM16 to disk until the user stops it; model inference begins only after capture closes.
- Session watcher: drain lanes, close files, and write the final receipt.

## Invariants

1. No inference or file dialog runs inside the audio callback.
2. No consumer can evict audio needed by another consumer.
3. Any actual input overflow is fatal and observable; it is never relabelled as normal progress.
4. Source timestamps derive from committed 16 kHz sample counts, not wall time.
5. Frozen H2 thresholds are copied with provenance and are not adjusted by the demo.
6. Model downloads are disabled; every asset is checksum validated.
7. Enrollment profiles are local, backend/checkpoint specific, and quality checked.
8. The GUI owns presentation only; CLI and GUI call the same runtime.
9. Loading indicators follow backend lifecycle events, and displayed timers derive from committed audio frames rather than button-click wall time.
10. Raw ASR text is immutable; learned punctuation is a separately identified display/export field.

## Future XVF3800 integration

An XVF adapter will implement `SpatialEvidenceProvider` and align energy, AoA, AoA confidence, and direction changes to the audio sample clock. Its raw events should be recorded before any fusion. Result-affecting policies must be separate, versioned implementations so the following ablations remain possible:

- audio only;
- audio + energy;
- audio + AoA;
- audio + energy + AoA;
- processed XVF audio + metadata.

Candidate future policies include boundary assistance, cluster association priors, and identity weighting. They must never change capture or raw-event preservation.

## Future interface work

Presentation listens only to `PipelineEvent`, so transcript cards, animated speaker indicators, room-angle views, and alternate displays can be replaced without touching audio or inference. User view should continue to show plain tentative/confirmed wording; raw scores and margins belong in research view.
