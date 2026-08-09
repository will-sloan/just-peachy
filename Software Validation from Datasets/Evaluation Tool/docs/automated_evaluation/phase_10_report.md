# Phase 10 — Speaker Enrollment, Verification, Identification, and Unknown Rejection

## Outcome

Stage 10 is implemented for ECAPA and all three Stage 9-qualified extended embedding backends: Resemblyzer, Sherpa-ONNX speaker embeddings, and WeSpeaker. Enrollment artifacts are backend-specific and cryptographically bound to model, asset, config, dimension, normalization, preprocessing, aggregation, and threshold-policy identities.

The immutable small, standard, and large protocol tiers are published under `benchmarks/stage10/`. Every tier passes enrollment/probe, calibration/evaluation, and unknown-speaker leakage checks. Shared speaker identities are deterministic pseudonyms; no private real-name mapping is present.

## Released manifests

| Tier | Enrollment | Calibration | Known evaluation | Unknown evaluation | Clean probes | Degraded probes |
|---|---:|---:|---:|---:|---:|---:|
| small | 18 | 34 | 36 | 20 | 45 | 45 |
| standard | 60 | 136 | 144 | 80 | 180 | 180 |
| large | 60 | 340 | 360 | 200 | 450 | 450 |

Clean and degraded probe counts are views of the split manifests, not additional source selections.

## Implemented outputs and metrics

- Typed embedding and centroid NPZ files with pickle disabled.
- Embedding and enrollment indexes.
- Pairwise cosine scores and calibration/evaluation threshold sweeps.
- Calibration-only operating threshold and explicit acceptance policy.
- Verification decisions, identification rankings, and `Unknown` rejection decisions.
- Failure records that remain in metric denominators.
- EER, FAR, FRR, TAR at fixed FAR, ROC/DET data, top-k identification, unknown rejection, false-known assignment, score distributions, extraction/enrollment failures, clean-to-degraded drift, and grouped metrics.
- Counts and deterministic 95% Wilson/bootstrap confidence intervals.
- Complete SHA-256 result validation.

## Validation

- Stage 10 tests: 16 passed.
- Real contract smoke: 4/4 backends passed, eight identical clean protocol items per backend, 32 real embeddings total.
- ECAPA, Resemblyzer, Sherpa-ONNX, and WeSpeaker each completed extraction, enrollment, calibration, held-out evaluation, and result validation.
- Affected regressions passed: legacy speaker/enrollment (34), Stage 0 (9), Stage 1 (21), Stage 2 (35), Stage 3 (26), and Stage 9 (17).
- `Unknown` is preserved exactly. Failed probes cannot receive unknown-rejection credit.
- Reference identity fallback is prohibited and tested.
- No implicit downloads or pickle artifacts were used.

## Scientific execution boundary

The real smoke qualifies contracts and composition; it is not a full clean/degraded scientific comparison. Full degraded evaluation must use the existing campaign augmentation path and approved noise/RIR scenarios, preserving the Stage 10 item IDs. Standard and large execution remain later campaign operations. Diarization science remains Stage 11.
