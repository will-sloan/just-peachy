# Speaker Embedding Component Report

## Milestone

M9 - Speaker Embedding Interface and First Adapter

- Run id: `m9_speaker_embedding`
- Selected backend for local smoke: `fake_speaker_embedding`
- Real adapter status: implemented and unit-tested with an injected encoder; not executed with real SpeechBrain ECAPA weights because SpeechBrain is not installed in the active `.venv`.

## Files Changed

- `app/inference_pipeline/speaker_embedding/__init__.py`
- `app/inference_pipeline/speaker_embedding/base.py`
- `app/inference_pipeline/speaker_embedding/report.py`
- `app/inference_pipeline/speaker_embedding/speechbrain_adapter.py`
- `configs/inference/components/speaker_embedding/speechbrain_ecapa.yaml`
- `scripts/embed_speaker_folder.py`
- `tests/inference_pipeline/test_speaker_embedding_interface.py`
- `tests/run_all_tests.py`
- `reports/component_reports/speaker_embedding/embedding_quality_m9_speaker_embedding.md`

## Summary

M9 adds a modular `SpeakerEmbeddingBase.embed(audio_segment, context) -> SpeakerEmbedding` interface with serializable, L2-normalized embedding results. The result metadata includes model name, dimension, segment duration, device, runtime statistics, reliability status, source identity, timestamps, sample rate, and adapter metadata.

The milestone also adds:

- `DeterministicFakeSpeakerEmbedding` for stable tests and smoke checks.
- `SpeechBrainECAPAAdapter` as a lazy PyTorch-native backend boundary.
- JSONL/parquet folder embedding script with runtime, memory, short-segment, and similarity summaries.
- Similarity distribution helpers for same-speaker and different-speaker cosine comparisons.

## How The Component Works

The adapter receives an existing `AudioSegment` and `SpeakerEmbeddingContext`. The context preserves `recording_id`, `utt_id`, segment index, start/end timestamps, device, dtype, and run configuration. Successful embeddings are normalized before `SpeakerEmbedding` construction, and `SpeakerEmbedding` validates that successful vectors are non-empty and L2-normalized.

Segments shorter than `min_duration_sec` are flagged with `status="too_short"` and `reliable=false` instead of producing a misleading vector. The SpeechBrain adapter loads audio from `audio_segment.audio_path`, respects `start_sec` and `end_sec`, converts to mono, resamples to the configured sample rate, and lazily loads `EncoderClassifier` only when `embed()` is called.

## Runner Contract Preservation

No changes were made to `app/model_runner/external_stub.py`, `PipelineRunner` prediction output, scorer, GUI, CLI, dataset registry, or report generator. Existing prediction identity and field-contract tests passed. The standalone speaker embedding script writes embedding artifacts only; it does not modify `predictions/utterances.jsonl`.

## Commands Run

- `../../.venv/bin/python -m pip show speechbrain`
- `../../.venv/bin/python -m pytest tests/inference_pipeline/test_speaker_embedding_interface.py`
- `../../.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py tests/inference_pipeline/test_speaker_embedding_interface.py`
- `../../.venv/bin/python -m pytest tests/inference_pipeline/test_contracts.py tests/model_runner/test_external_stub_bridge.py`
- `../../.venv/bin/python scripts/embed_speaker_folder.py /private/tmp/m9_speaker_embedding_smoke/audio --backend fake --output /private/tmp/m9_speaker_embedding_smoke/embeddings.jsonl --report /private/tmp/m9_speaker_embedding_smoke/embedding_quality_smoke.md --labels-csv /private/tmp/m9_speaker_embedding_smoke/labels.csv --dimension 8 --min-duration-sec 0.1 --run-id m9_smoke`
- `../../.venv/bin/python -m compileall app/inference_pipeline/speaker_embedding scripts/embed_speaker_folder.py`

## Test Results

- M9 interface tests: `9 passed`
- Config registry plus M9 tests: `19 passed`
- Existing contract plus external stub bridge tests: `15 passed`
- Compile check: passed

## Validation Checks

- Dimension checks: fake adapter produced dimension `8`; injected SpeechBrain encoder produced configured dimension `3`; short segments produced dimension `0` with `status="too_short"`.
- Normalization checks: unit tests assert L2 normalization; script smoke output had norm range `1.0000` to `1.0000`.
- Serialization checks: `SpeakerEmbedding.to_jsonable()` round-trips through JSON and `SpeakerEmbedding.from_jsonable()`; folder script wrote `3` JSONL rows.
- Runtime RTF: fake smoke report showed mean and max RTF rounded to `0.0000`; raw JSONL rows recorded non-null per-row RTF values.
- Memory: fake smoke report recorded max CPU memory `327.81 MB`.
- Short-segment failure/flag rate: unit test covers one too-short segment; smoke run had `0/3` too-short rows.

## Similarity Distribution

The smoke distribution used deterministic fake embeddings, so it proves report plumbing but not real speaker quality.

- Same-speaker pairs: `1`
- Different-speaker pairs: `2`
- Same-speaker mean cosine: `0.2827`
- Different-speaker mean cosine: `0.0822`
- Same-speaker min/max cosine: `0.2827` / `0.2827`
- Different-speaker min/max cosine: `0.0792` / `0.0852`

## Blockers

- `speechbrain` is not installed in the active repository `.venv`; `../../.venv/bin/python -m pip show speechbrain` reported `Package(s) not found: speechbrain`.
- Local SpeechBrain ECAPA model assets were not found or validated. The adapter intentionally refuses implicit downloads unless `allow_model_downloads` is enabled.
- Because of the missing dependency/assets, a real SpeechBrain ECAPA run on labeled data was not completed.

## Incomplete

- Install SpeechBrain in the repository `.venv` and provide local ECAPA assets, or explicitly allow model downloads in a controlled environment.
- Run `scripts/embed_speaker_folder.py --backend speechbrain` on a small labeled sample and replace the fake similarity distribution with real same-speaker and different-speaker separation.
- Use the resulting report to choose downstream thresholds for future speaker matching.
