# Speaker Embedding Component Report

## Milestone

M9 - Speaker Embedding Interface and First Adapter

- Run id: `m9_speechbrain_cached`
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

- `python scripts/embed_speaker_folder.py m9_test/audio --backend speechbrain --output m9_test/speechbrain_embeddings_cached.jsonl --report m9_test/speechbrain_embedding_cached.md --dimension 16 --min-duration-sec 0.1 --run-id m9_speechbrain_cached`

## Validation Checks

- Dimension checks: successful dimensions=[192]
- Normalization checks: min_norm=1.0000, max_norm=1.0000
- Serialization checks: wrote 3 row(s) to m9_test/speechbrain_embeddings_cached.jsonl
- Runtime RTF: mean=0.0061, max=0.0070
- Memory: max_cpu_memory_mb=2435.39
- Short-segment failure/flag rate: 0/3 (0.0000)

## Similarity Distribution

- Not available for this run.

## Blockers

- None known.

## Incomplete

- No labels CSV was supplied, so same-speaker vs different-speaker separation is unavailable.
