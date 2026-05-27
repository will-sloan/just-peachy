# Speaker Embedding Component Report

## Milestone

M9 - Speaker Embedding Interface and First Adapter

- Run id: `m9_speechbrain_local`
- Selected backend: `speechbrain_ecapa`
- Real adapter status: ran successfully for 3 row(s)

## Files Changed

- `scripts/embed_speaker_folder.py`

## Summary

M9 adds a swappable speaker embedding interface, a deterministic fake adapter,
and a lazy SpeechBrain ECAPA adapter boundary that produces normalized vectors
when local model assets are available.

## Runner Contract Preservation

Standalone speaker embedding script does not modify predictions/utterances.jsonl or the Evaluation Tool runner contract.

## Commands

- `python scripts/embed_speaker_folder.py m9_test/audio --backend speechbrain --output m9_test/speechbrain_embeddings.jsonl --report m9_test/speechbrain_embedding_quality.md --dimension 16 --min-duration-sec 0.1 --labels-csv m9_test/labels.csv --run-id m9_speechbrain_local --allow-model-downloads`

## Validation Checks

- Dimension checks: successful dimensions=[192]
- Normalization checks: min_norm=1.0000, max_norm=1.0000
- Serialization checks: wrote 3 row(s) to m9_test/speechbrain_embeddings.jsonl
- Runtime RTF: mean=0.0076, max=0.0112
- Memory: max_cpu_memory_mb=2393.94
- Short-segment failure/flag rate: 0/3 (0.0000)

## Similarity Distribution

- Same-speaker pairs: `1`
- Different-speaker pairs: `2`
- Same-speaker mean cosine: `1.0000`
- Different-speaker mean cosine: `1.0000`
- Same-speaker min/max cosine: `1.0000` / `1.0000`
- Different-speaker min/max cosine: `1.0000` / `1.0000`

## Blockers

- None known.

## Incomplete

- None known.
