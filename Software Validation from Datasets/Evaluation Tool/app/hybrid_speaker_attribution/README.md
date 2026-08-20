# Hybrid speaker attribution

## Purpose

This package evaluates the combination of the frozen controlled-diarization
benchmark and a qualified speaker-embedding backend. It measures whether
anonymous diarization clusters can be assigned exact enrolled identities or
persistent recording-local `Unknown_N` identities. It does not run ASR and does
not alter the controlled waveforms or anonymous diarization scores.

The engineering-only smoke policy is
`configs/automated_evaluation/hybrid_enrollment_policy.non_scientific_smoke.yaml`.
It is deliberately marked non-scientific. Scientific development requires an
operator-supplied policy frozen from the speaker enrollment-duration study.

## Inputs

- `benchmarks/stage11/controlled_diarization_v1`: frozen case manifests,
  references, recipes, and original identity-overlay source metadata.
- `benchmarks/hybrid_speaker_attribution/hybrid_speaker_attribution_v1`: the
  generated metadata-only overlay protocol.
- `JP_GENERATED_DATA_ROOT/controlled_diarization_v1`: unchanged controlled WAVs.
- Reserved Common Voice enrollment clips resolved through `JP_DATA_ROOT`.
- One runtime-selected qualified speaker backend and one runtime-selected
  controlled diarization pipeline.
- One `hybrid-enrollment-policy.v1` YAML policy.
- Existing or newly generated controlled diarization result folders.

## Outputs

The default result root is
`%USERPROFILE%\JustPeachyResults\hybrid_speaker_attribution`. Each case/overlay
contains exact configuration, diarization, backend and enrollment identities;
final and progressive predictions; future-ASR-compatible turn rows with
`text: null`/`asr_status: NOT_RUN`; metrics; oracle-diarization diagnostics;
resource data; and checksums. Embeddings are cached outside result units and
are keyed only by audio/interval/backend identity, so rescoring never reruns a
model.

Analysis writes the predeclared CSV/JSON/Markdown tables documented in
`docs/automated_evaluation/hybrid_speaker_attribution.md`. `Collect` excludes
audio, model files, and the embedding cache.

## Anaconda Prompt / Command Prompt

From the repository root:

```bat
call .venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python run_evaluation.py hybrid-attribution --help
python -m pytest tests\hybrid_speaker_attribution -q -p no:cacheprovider
```

To create the metadata-only protocol without inference:

```bat
python run_evaluation.py hybrid-attribution prepare
python run_evaluation.py hybrid-attribution validate
```

## PowerShell

From the repository root, audit a concrete selection without inference:

```powershell
$Tool = "Software Validation from Datasets\Evaluation Tool"
powershell -ExecutionPolicy Bypass -File "$Tool\scripts\run_hybrid_speaker_attribution.ps1" `
  -Action Audit `
  -SpeakerBackend "campplus_speaker_embedding" `
  -DiarizationPipeline "sherpa_onnx_diarization" `
  -EnrollmentPolicy "$Tool\configs\automated_evaluation\hybrid_enrollment_policy.non_scientific_smoke.yaml"
```

Run only the bounded non-scientific smoke by adding `-Action Smoke -MaxCases 1`.
Development and evaluation commands require a scientifically selected policy.
`RunEvaluation` additionally refuses to start without matching frozen hybrid
and diarization configuration files and rejects ad hoc parameter overrides.

## Principal interfaces

- `protocol.py`: creates and validates immutable metadata overlays.
- `embedding_cache.py`: runs the selected backend in its isolated environment
  and publishes restart-safe per-segment cache records.
- `attribution.py`: deterministic final/progressive decisions and scoring.
- `runner.py`: gating, reuse, result contracts, smoke/development/evaluation.
- `analysis.py`: read-only tables, reliability summaries, and compact collection.
- `cli.py`: `hybrid-attribution` command registration.

Unknown labels are assigned by first cluster appearance within each recording.
Known identities are scored exactly; only unknown reference identities receive
an optimal recording-local mapping. Reference labels never split a predicted
cluster and never rewrite anonymous diarization output.
