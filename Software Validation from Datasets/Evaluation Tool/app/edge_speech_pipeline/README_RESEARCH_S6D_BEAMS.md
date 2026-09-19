# S6D accepted capture beam integration

Purpose: research_beams_s6d.py adds opt-in native analysis of accepted same-pass multistream captures. One continuous mono auto ASR decoder consumes only its admitted auto waveform. One serial owner shares the existing Pyannote/ReDimNet weights across an auto speech gate and at most two focused identity lanes. Each focus has independent evidence admission, tracker, identity resolver and rolling audio. Existing defaults, frozen native pilot v3 and independently reviewed GUI v3 remain separate.

This implemented engine/CLI interface has model-free fixtures. It is not a measured native beam result or physical qualification. Import, fixtures, manifest preparation and --check-only start no neural models/devices. New captured waveforms require new native predictions; old O0/O1 predictions are never substituted.

## Inputs and admission

BeamSettings JSON uses schema_version edge-s6d-beams.v1, explicit mode, asr_stream (auto_asr or auto_pp), identity_streams, selected_profile_ids, maximum_evidence_age_sec (default0.75; finite, greater than0, at most2), and an optional exact calibration binding.

- same_pass_auto_control: identity_streams contains only that auto stream; invokes the original v3 dual-window identity lane and one common journal.
- mono_asr_beam_identity: at most one stream from each of focus0/focus1; mature focused embeddings reach the main transcript scheduler only with calibrated, exclusive, same-window auto waveform support.
- selected_beam_association: same continuous auto transcript plus selected-person association events. Selected IDs must belong to the exact admitted gallery. Selection does not splice audio or create a second transcript.
- calibration_collection: focused native evidence collection with both selectors disabled; requires a separately bound disjoint-C proof. It needs no selector calibration and is not scored as a beam-family performance experiment.

ASR/PP copies of one beam cannot become two identity lanes. No six permanent model stacks are created. Inputs never switch, so unrelated waveforms never share mutable decoder state. Actual beam-ASR switching and its independent decoder-state lifecycle are outside this interface.

Every file binding is an exact {path, bytes, sha256} object with a resolved absolute path. An edge-s6d-capture-admission.v1 JSON requires status ACCEPTED_FOR_NATIVE_ANALYSIS; capture_source_id, route_id, capture_epoch, common_origin; case_result/configuration/qualification bindings; sample_count; and stream_names in actual capture order. The case result must report PASS and transport_integrity_status PASS. Independent qualification uses schema edge-s6d-route-qualification.v1, status PASS, binds that exact case_result/configuration, lists qualified streams, and explicitly verifies stream_identity_verified/common_frame_origin_verified/source_tail_validity_verified. Transport-only PASS is insufficient.

Configuration profile must be P_MAIN6 or P_SCAN6. Requested stream records bind unchanged lossless mono16k audio, unity raw_gain, expected category/source routing (auto ASR7/3, auto PP6/3, focus ASR7/0–1, focus PP6/0–1), a common nonnegative integer native-frame origin and equal complete sample counts. No resampling, downmix, independent trim, warp or gain adjustment occurs. Original lossless captures remain intact; the existing AudioJournal quantizes model input to PCM16 once. Same-pass controls use the same representation.

Optional direction_observations bind capture_source_id/route_id and separate source_support_qualification (schema edge-s6d-spatial-source-qualification.v1, PASS, same case_result, source_span_not_reply_time_only true). Individual observations still need finite source span, availability, calibrated confidence and supported direction source. Reply time and matching wall time cannot invent DSP source support. Missing spatial evidence leaves arrows unavailable. Native speech/voice IDs bind only their compatible captured stream; direction policy requires a common observation/speech/voice intersection and rejects stale or cross-session support.

## C-only calibration

Selector calibration is separate from the unchanged gallery's single-query name thresholds. Schema edge-s6d-beam-calibration.v1, status ACCEPTED_C_ONLY, binds the exact gallery manifest and calibration_evidence proof; exact canonical v3 profile_sha256, capture_profile, identity_streams and selected_profile_ids; finite0–1 minimum_selected_score, minimum_selected_margin, minimum_beam_margin, minimum_auto_correlation and minimum_auto_margin. Proof declares partition C, Q_used false and disjoint_from_E_Q_verified true. Actual acquisition/scoring references and sample-size limits require independent review before assigning that accepted status.

Duplicate resolution is separately scoped: duplicate_resolution_enabled defaults false. Enabling it also requires duplicate_waveform_correlation, duplicate_voice_cosine and continuity_bonus, no larger than minimum_beam_margin. A duplicate requires the same confirmed profile, same source window, sufficiently similar waveform and voice. Energy or a repeated name never suffices. No unique duration is summed across copies. Unsupported duplicate calibration can stay disabled while core association is evaluated.

Both source-end freshness and actual evidence availability must satisfy the bounded clock horizon: late publication cannot renew stale source support. Auto/focus association requires identical windows within one16k sample, clean exclusive auto speech, calibrated correlation floor and lead over other beams. Missing calibration, speech, clock, confidence or route evidence produces NO_MATCH. This is association evidence, not acoustic separation.

The four planned whole-C passes (MAIN/SCAN × R04/R12) and already budgeted same-C two-path/ABA/overlap/source-swap controls can feed C collection after physical qualification. Sequential30-person C cannot establish simultaneous competition; the two-person overlap controls provide narrow coverage. C collection also binds calibration_partition: schema edge-s6d-beam-calibration-partition.v1, partition C, Q_used false, verified E/Q disjointness, and accepted_case_results containing the exact physical case-result binding. Prepared uncaptured inputs do not qualify; a new proof epoch must add accepted outputs. Thresholds remain pending until fixed-model C evidence is collected and reviewed. No Q tuning.

## Outputs and measurement limits

Normal sessions write complete unfiltered events/transcript exports, bounded asynchronous journals and consumer closure receipts. Additional events include s6d_beam_input_route, s6d_beam_speech, s6d_beam_embedding_admission, s6d_beam_identity, s6d_selected_beam_association and s6d_auto_beam_association. Every voice/speech event carries capture/route/stream/source-clock evidence. The main bridge is mature-only; short focus observations aid each lane's identity. This composite policy must not be attributed solely to routing or described as unchanged v3 identity behavior.

Telemetry records configured model/state counts, actual API calls/wall time, separate identity-policy time, source cursor/backlog, serial owner ID and per-beam resolver state. No separate model executor queue exists: model_queue_depth is0 for the serial owner, while source_queue_age_sec reports actual waiting audio. Startup/warmup is separate from source_started. The source commits100ms to all journals before sleeping100ms, so first-block source-end deltas may be approximately−0.1s. Final consumer/journal drains remain mandatory.

Frozen native pilot v3 showed C105 repaired naming p95 additional delay+0.398s in the small08_07 pair, exceeding the declared+0.25s goal. Three utterances per pair and scheduling variation do not support generalized speedup or promotion; these are not beam measurements. GUI v3 model-free closure does not establish native beam/physical qualification.

## Model-free fixture commands

Inputs: temporary synthetic WAVs/receipts and fake ASR/model objects. Outputs: unittest results and temporary actual engine journals. No neural models/devices run; synthetic proofs never enter the physical bank. Fixtures cover route/tail/hash admission, missing/stale/future/cross-capture evidence, duplicate controls, calibrated positive association, auto-only decoder, shared owner, original same-pass control, C collection and frozen CLI input tamper rejection.

PowerShell:
~~~powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m app.edge_speech_pipeline.checks_research_beams_s6d
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m app.edge_speech_pipeline capture --help
~~~

Anaconda Prompt / CMD (explicit existing interpreter avoids environment changes):
~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m app.edge_speech_pipeline.checks_research_beams_s6d
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m app.edge_speech_pipeline capture --help
~~~

## Exact future native CLI

Use simulation/scripts/s6d_application_beam_plan.py with README_S6D_APPLICATION_BEAM_PLAN.md. It emits complete argv, frozen PYTHONPATH, fixed-eight-asset manifest, session root, input receipt and receipt SHA. The CLI validates all six input bindings before model creation. Constructors verify actual weight SHA once at startup; planning does not hash multiGB weights in a supervisor loop.

~~~text
python -B -m edge_speech_pipeline capture ADMISSION.json --beam-settings BEAM.json --research-profile PROFILE.json --research-gallery GALLERY.json --s6d-settings S6D.json --asset-manifest ASSETS.json --session-root SESSION_ROOT --input-bindings JOB_INPUTS.json --input-bindings-sha256 EXACT_SHA --check-only
~~~

Use exact model_free_admission_argv for checks and exact argv only after source/matrix/supervisor review. Removing --check-only starts fixed-model file analysis, not hardware. No native execution is authorized by this README. Empty plans contain zero admitted jobs, not invented results.

## Rejected-restart repair epoch

Beam interface v2's independent review reproduced one adverse case: attempting B while A ran replaced A's capture/selector/source origin before inherited session admission rejected B. The additive repair rejects active states before reading B and keeps a validated candidate capture/selector local until inherited enrollment-recorder, finalization and previous-consumer-closure guards succeed. Rejected attempts preserve the previous provenance, selector, source clock, stream views and event inbox. The independently supplied five probes remain unchanged; additional author fixtures cover RUNNING/PAUSED/LOADING/STOPPING and all four inherited restart guards. This changes admission ordering only, with no model, waveform, calibration, routing or default change.

For this repair review, set TEMP and TMP to a fresh G run review child before invoking Python so all temporary synthetic data and results remain on G. The new frozen epoch includes exact source differences and the unchanged independent probe; old v2 source/adverse evidence remains retained. A future native supervisor must additionally require full admitted capture-frame consumption and all drains: an intentionally stopped prefix can close cleanly and must not be reported as a complete full-input experiment merely because the inherited engine state is COMPLETED.
