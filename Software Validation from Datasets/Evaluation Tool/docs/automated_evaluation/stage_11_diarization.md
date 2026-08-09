# Stage 11 — Diarization and Native-Condition Evaluation

Stage 11 adds a versioned native diarization layer without changing dataset loading, augmentation, inference adapters, ASR scoring, GUI behavior, or existing runners.

## Scientific boundary

The native manifest is a deterministic view of the frozen Stage 2 `native_robustness` panel. Every unit preserves its original recording, utterance, source bounds, meeting/session, stream, channel, microphone/device, and native-condition metadata. Synthetic noise and RIR fields are rejected.

AMI and CHiME-6 provide compatible bounded timing references. AMI headset and CHiME-6 participant-close units are explicitly wearer-only references; they do not claim meeting-wide confusion coverage. VOiCES remains useful for room, distractor, microphone, position, and reliability comparisons, but its current normalized metadata does not justify DER/JER. The scorer therefore returns a machine-readable suppression reason and omits DER/JER keys.

## Label and segmentation semantics

Predictions use backend-local `speaker_*` labels. A global permutation is computed internally for scoring, but it never rewrites stored labels or creates named identities. Known-speaker matching, embeddings, speaker-change detection, and full anonymous diarization remain distinct concepts.

Segmentation provenance records configured and effective sources. For Sherpa-ONNX the effective source is `backend_internal`; no external VAD is credited. Oracle segmentation is accepted only as a separately labelled diagnostic. Oracle speaker count is also recorded as a different diagnostic mode and must not be pooled with estimated-count results.

## Scoring policy

The v1 policy records a 0.25-second collar, both overlap-aware and overlap-excluded results, exact UEM regions, source-absolute time, the reference version, estimated/oracle speaker-count mode, and `diarization-scoring-policy.v1`. DER components are missed speaker-time, false-alarm speaker-time, and speaker confusion after one-to-one optimal anonymous-label alignment. JER and anonymous-label consistency use the same evaluated timebase. cpWER is available only when complete, correctly attributed transcript references and hypotheses exist.

## Qualification outcome

Sherpa-ONNX is the only backend currently qualified and executable. pyannote and Falcon retain `licence_action_required`; NeMo retains `platform_required`. These are explicit availability results, not failures hidden from reports. No backend may download a model or obtain credentials during execution.
