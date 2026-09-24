# N2 four-way saved-audio screen

Status: **COMPLETE**. Scored 384 of 384 expected cells; 96 cells are matched across all four combinations. Missing and failed cells remain in the denominator.

| Combination | Scored / expected | Missing |
| --- | ---: | ---: |
| D0_E0 | 96 / 96 | 0 |
| D1_E0 | 96 / 96 | 0 |
| D0_E1 | 96 / 96 | 0 |
| D1_E1 | 96 / 96 | 0 |

ASR invariance: **PASS_ALL_MATCHED**. Exact raw observation/final-word, source dispatch/reset and formatted-final checks are reported separately against matched D0/E0 cells.

Activity DER/JER use estimated 20 ms references: zero-collar primary and 250 ms sensitivity with retained speaker-time denominators. D0 full activity scores remain unavailable. cpWER retains Unknown streams and uses complete reference scenes; tcpWER remains unavailable. First-visible, first-final and latest caption stages stay separate.

CPU/CUDA runtime identities are separate strata. Resource counts include process work and any observer work; they do not establish Pi performance, total 2 GB suitability or an isolated GPU benchmark. Full aggregate denominators, source-turn coverage, strangers, missing enrollment, closed assumptions and queue measurements are in SCREEN_SUMMARY.json. Private cell evidence is retained outside Git.
