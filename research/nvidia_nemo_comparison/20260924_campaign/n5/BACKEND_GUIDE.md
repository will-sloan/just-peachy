# Backend availability and interpretation

| Composition | Purpose / tradeoff | N5 availability |
|---|---|---|
| A0/D0/E0 preserved baseline | Current Sherpa Giga + Pyannote + ReDimNet + final-only punctuation; known application reference | Windows N1 shortcut; baseline offline target bundle prepared |
| A0/D1/E0 | Isolates Nemotron diarization without changing ASR/embedding | N2 screen/regressions complete; N4 selection pending |
| A0/D0/E1 or A0/D1/E1 | TitaNet comparator in its own embedding space | N2 screen/regressions complete; D0/E1 association-scale calibration and N4 acceptance pending |
| A1 combinations | Parakeet realtime EOU 120M, potentially compact ASR | Standalone reference/export attempt queued in N3; integrated/portable route not established |
| A2/A3 combinations | Native stateful 600M ASR with native casing/punctuation | Windows integration prepared; CPU ARM64 runtime built; numerical/model-load acceptance pending |
| X1 multitalker | Optional high-compute overlap contrast | DEFERRED; not a release |

All numerical strengths/weaknesses remain unranked until exact N4 combinations
are scored. Smooth UI or clean process exit does not establish accuracy. The
new native archive is infrastructure for a portable alternative, not proof that
one runs correctly or fits 2GB. No new candidate is silently substituted into
the baseline, and failed loading must surface an error.

All final retained general profiles require 240 scenes × both taps. At this
checkpoint N4 scored 0 of its planned 7,680 combination/cell entries. Completed
N2 subsets and wiring tests are separately scoped and cannot fill those rows.
See ../n4/MATRIX.json, ../n4/N4_HANDOFF.md and the live private status files.
