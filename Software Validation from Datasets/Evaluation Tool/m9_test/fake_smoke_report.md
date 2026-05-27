# Speaker Embedding Component Report

## Milestone

M9 - Speaker Embedding Interface and First Adapter

- Run id: `m9_fake_smoke`
- Selected backend: `fake_speaker_embedding`
- Real adapter status: not selected; fake backend used for deterministic smoke check

## Files Changed

- `scripts/embed_speaker_folder.py`

## Summary

M9 adds a swappable speaker embedding interface, a deterministic fake adapter,
and a lazy SpeechBrain ECAPA adapter boundary that produces normalized vectors
when local model assets are available.

## Runner Contract Preservation

Standalone speaker embedding script does not modify predictions/utterances.jsonl or the Evaluation Tool runner contract.

## Commands

- `python scripts/embed_speaker_folder.py m9_test/audio --backend fake --output m9_test/fake_smoke_embeddings.jsonl --report m9_test/fake_smoke_report.md --dimension 8 --min-duration-sec 0.1 --labels-csv m9_test/labels.csv --run-id m9_fake_smoke`

## Validation Checks

- Dimension checks: successful dimensions=[8]
- Normalization checks: min_norm=1.0000, max_norm=1.0000
- Serialization checks: wrote 3 row(s) to m9_test/fake_smoke_embeddings.jsonl
- Runtime RTF: mean=0.0000, max=0.0000
- Memory: max_cpu_memory_mb=328.00
- Short-segment failure/flag rate: 0/3 (0.0000)

## Similarity Distribution

- Same-speaker pairs: `1`
- Different-speaker pairs: `2`
- Same-speaker mean cosine: `-0.2294`
- Different-speaker mean cosine: `-0.0445`
- Same-speaker min/max cosine: `-0.2294` / `-0.2294`
- Different-speaker min/max cosine: `-0.1472` / `0.0581`

## Blockers

- SpeechBrain ECAPA was not executed by this script run. Use --backend speechbrain with installed package and local model assets to validate the real adapter.

## Incomplete

- Real SpeechBrain ECAPA quality separation remains unvalidated in this run.
