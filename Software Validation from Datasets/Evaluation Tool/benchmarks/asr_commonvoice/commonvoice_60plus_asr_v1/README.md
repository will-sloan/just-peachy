# Frozen Common Voice 60+ ASR protocol

This is the model-independent ASR view of the existing frozen speaker-breadth
selection. It contains exactly 11685 English clips from
413 pseudonymous speakers and no audio or raw Common
Voice client identifiers. `manifest.parquet` is authoritative; `manifest.tsv`
is its human-readable copy. References came from the frozen read-only source
database and were hash-checked against `source_selection.tsv`.

Protocol ID: `commonvoice_60plus_asr_v1_fb22c247f5f7`

Scoring lowercases text, removes ASCII punctuation, strips outer whitespace,
and collapses internal whitespace identically for reference and hypothesis.
No augmentation is used. Physical audio paths resolve through `JP_DATA_ROOT`.
This protocol is not a redistribution grant for Common Voice audio.
