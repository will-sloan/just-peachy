# Phase 11 Report — Diarization and Native-Condition Evaluation

## Outcome

Stage 11 is implemented as an additive execution and evaluation layer. It uses the existing Stage 2 manifests, normalized metadata, component catalog, audio loader, and diarization adapters. Existing dataset loading, augmentation, configured/external/simulation runners, ASR scoring, plotting, reporting, GUI, and prior stage contracts were not replaced.

## Released native views

The immutable outputs under `benchmarks/stage11/` contain:

| Tier | Units | AMI | CHiME-6 | VOiCES | DER/JER eligible | cpWER-reference eligible |
|---|---:|---:|---:|---:|---:|---:|
| small | 200 | 80 | 80 | 40 | 160 | 44 |
| standard | 1,118 | 518 | 480 | 120 | 998 | 322 |
| large | 5,808 | 3,168 | 2,400 | 240 | 5,568 | 1,584 |

All units are `native_only`, use source-recording absolute seconds, preserve available meeting/session/stream/channel/microphone/device/location fields, and retain the frozen Stage 2 manifest hash. VOiCES rows deliberately remain DER/JER-ineligible because no compatible fine-grained speech timing is present. cpWER eligibility indicates only that complete reference segment text survived the bounded view; a score still requires real speaker-attributed ASR hypotheses.

## Backend qualification and availability

| Backend | Frozen prerequisite status | Current Stage 11 action |
|---|---|---|
| Sherpa-ONNX diarization | `qualified` | Real bounded AMI contract smoke passed in the ONNX environment; eligible for native campaign execution. |
| pyannote community | `licence_action_required` | Not run. Requires accepted gated terms, `PYANNOTE_LICENSE_ACCEPTED`, `PYANNOTE_AUTH_TOKEN`, package/assets, and requalification. |
| Picovoice Falcon | `licence_action_required` | Not run. Requires accepted terms, `PICOVOICE_LICENSE_ACCEPTED`, `PICOVOICE_ACCESS_KEY`, package, and requalification. |
| NeMo diarization | `platform_required` | Not run on Windows. Requires Linux/CUDA, local active model/config assets, and requalification. |

No credentials or models were acquired automatically. Status artifacts contain only boolean credential/licence presence, not secret values.

The real smoke evidence is `runs/diarization_evaluation/smoke_summary.json` and scenario `smoke_sherpa_onnx_diarization_diar_0e112c574a82`. It produced validated anonymous RTTM, source-aligned UEM/reference slices, effective `backend_internal` segmentation provenance, checksums, metrics, and reports. Its score is a contract smoke on one short bounded unit, not a scientific performance conclusion.

## Scientific safeguards

- RTTM and UEM parsing fails on malformed rows instead of silently ignoring them.
- Reference and prediction file IDs/timebases are validated before metrics are emitted.
- DER uses exact atomic intervals, one-to-one optimal speaker permutation, explicit missed speech, false alarm, and confusion terms.
- Both overlap-aware and overlap-excluded results are emitted with the released 0.25-second collar and exact UEM.
- JER, speaker-count error, and anonymous-label consistency share the same evaluated region.
- Invalid/incompatible pairs omit DER/JER keys and retain machine-readable suppression reasons.
- Stored anonymous `speaker_*` labels are never rewritten to reference identities.
- External VAD is not credited when backend-internal diarization controls segmentation.
- Oracle segmentation is diagnostic-only. Oracle speaker count is also a separate mode and is not pooled with estimated-count results.
- Native result aggregation retains suppressed and failed/missing denominators and groups by available dataset, meeting/session, stream, channel, microphone/device, and condition fields.

## Verification

The Stage 11 suite passed:

```text
19 passed
```

It covers RTTM parser/writer validation, malformed output, atomic metadata refresh, UEM, recording/channel timebase alignment, optimal permutation, overlap policy, collar policy, anonymous versus known semantics, provenance, cpWER, deterministic manifests, native augmentation rejection, backend status, synthetic execution bundles, VOiCES metric suppression, grouped analysis, schemas/CLI discovery, and preserved real Sherpa evidence.

Targeted regressions passed:

```text
58 passed
```

These include the existing diarization interface, Stage 1 configured runner, and Stage 10 speaker protocol. Ruff also reports no issues for the Stage 11 package, tests, or CLI integration.

## Deferred work

No standard or large diarization inference campaign was run. pyannote, Falcon, and NeMo remain unavailable until their user/platform prerequisites and real qualification are completed. Speaker-attributed transcripts, cpWER, and speaker-attributed WER remain conditional on real compatible ASR output. Performance claims require a later campaign run and grouped analysis over the released native views.
