# Phase 7 — Core Component Qualification and Screening

## Implemented scope

Stage 7 adds a versioned targeted-screening protocol, deterministic screening-plan/scenario generation, repeated real local component qualification, ASR/VAD/segmentation/embedding/reliability metrics, multi-objective advancement, and merged-result analysis. It uses Whisper Base as the VAD/segmentation reference and includes Whisper Tiny, Base, and Small as real ASR candidates.

The initial experiment contains 84 unique scenarios: three datasets, four small-tier smoke conditions, and seven unique B/C pipeline candidates. It does not generate all 15 ASR/segmentation combinations. Stage D remains pending until one or two segmentation candidates are named; only those candidates are crossed with qualified Whisper models. Final repetitions remain pending until finalists are named.

## Contract decisions

- The frozen `benchmark-manifest.v1`, `scenario-definition.v1`, canonicalization, and hash rules are reused unchanged.
- Component variants are resolved from the existing high-level YAML plus existing component fragments. Source YAML is never modified.
- Frozen scenarios contain complete resolved component/model identities. The campaign runtime can reconstruct declared component overrides from those identities and the selected source-config hash.
- VAD region rows are now included in per-item diagnostics. This is additive diagnostic data and does not change transcript predictions.
- Missing/failed output is scored as an empty hypothesis for primary Stage 7 WER/CER and remains separately counted. Duplicate, malformed, and unexpected rows remain visible.
- VAD reference metrics are emitted only when reference regions exist. The current controlled-clean manifest supports segment descriptives and downstream WER/CER but does not claim VAD precision/recall without reference regions.
- ECAPA qualification measures extraction success, dimensions, L2 norms, invalid vectors, repeatability, minimum-duration rejection, and optional paired drift. Stage 10 owns EER/FAR/FRR, identification, calibration, and unknown-rejection metrics.

## Advancement

Candidates must pass declared valid-output, failure, timeout, OOM, and repetition gates. Eligible candidates are compared by accuracy, reliability, robustness where available, and resources. Dominated candidates are removed. A deterministic shortlist cap preserves quality/reliability leaders before using aggregate tradeoff ranking, so speed alone cannot eliminate a model that offers a non-dominated benefit.

## Operator handoff

See `app/core_screening/README.md` for complete Anaconda Prompt, Command Prompt, and PowerShell commands, input/output paths, staged planning flow, and test commands.

## CPU qualification evidence

The repeated local CPU qualification artifact is `runs/component_qualification/stage7_core_cpu_20260807.json`. All nine scoped results qualified with two identical-input executions: full-record segmentation, Energy VAD, Silero VAD, VADChunker composition, Whisper Tiny, Whisper Base, Whisper Small, SpeechBrain ECAPA, and the cosine matcher contract/composition. The artifact records `0` unavailable and `0` failed results, confirms local-only model loading, and confirms that the empty-enrollment matcher path preserves `Unknown`. CUDA qualification remains a separate immediate follow-up gate and was not claimed by Stage 7 CPU evidence.
