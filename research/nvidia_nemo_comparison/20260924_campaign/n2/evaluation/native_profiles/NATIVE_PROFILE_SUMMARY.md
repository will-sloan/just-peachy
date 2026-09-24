# N2 native profile screen

Status: **COMPLETE**. Scored 288 of288 fixed cells; 96 match all three profiles. Device: cuda.

| Profile | Scored / expected |
| --- | ---: |
| low_latency | 96 /96 |
| very_low_latency | 96 /96 |
| ultra_low_latency | 96 /96 |

| Profile | Tap | Complete-reference cells | DER collar0 | Macro JER collar0 | DER collar250ms | Macro JER collar250ms | Retained speaker-time | Native wall/audio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| low_latency | O0 | 42 /48 | 23.80% | 21.24% | 3.83% | 5.19% | 21.52% | 0.0303 |
| low_latency | O1 | 42 /48 | 32.32% | 21.61% | 40.62% | 7.69% | 21.53% | 0.0303 |
| very_low_latency | O0 | 42 /48 | 23.83% | 20.91% | 4.81% | 6.31% | 21.52% | 0.0397 |
| very_low_latency | O1 | 42 /48 | 31.59% | 21.94% | 36.20% | 8.05% | 21.53% | 0.0396 |
| ultra_low_latency | O0 | 42 /48 | 24.40% | 21.40% | 6.36% | 6.64% | 21.52% | 0.0608 |
| ultra_low_latency | O1 | 42 /48 | 31.71% | 22.71% | 36.54% | 8.67% | 21.53% | 0.0610 |

DER/JER above are estimated activity diagnostics. JER averages supported nonempty scenes; its scene denominator is in JSON. Empty controls retain false activity seconds and a null individual DER denominator. Reference-class breakdowns expose those failures separately.

| Profile | Tap | Resolved / source turns | Resolved / short turns | Consistent / returns | Changed / unresolved returns | Split identities / merging slots |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| low_latency | O0 | 161 /161 | 28 /28 | 57 /59 | 2 /0 | 3 /5 |
| low_latency | O1 | 161 /161 | 28 /28 | 54 /59 | 5 /0 | 5 /6 |
| very_low_latency | O0 | 161 /161 | 28 /28 | 57 /59 | 2 /0 | 3 /4 |
| very_low_latency | O1 | 161 /161 | 28 /28 | 55 /59 | 4 /0 | 4 /4 |
| ultra_low_latency | O0 | 161 /161 | 28 /28 | 55 /59 | 4 /0 | 5 /7 |
| ultra_low_latency | O1 | 161 /161 | 28 /28 | 55 /59 | 4 /0 | 4 /5 |

Zero-collar estimated activity DER/JER are primary; 250ms sensitivity retains explicit speaker-time and wall-time exclusions. Missing/failed cells stay in the denominator. Raw native endpoint frames are preserved and scoring uses only delivered waveform support.

This is a pure native diarizer with accelerated causal input. It does not measure the application's ASR, embeddings, naming, caption latency, Pi behavior, GPU memory or total-system2GB suitability. Detailed turn/short/return/capacity counts and matched profile runtime ratios are in NATIVE_PROFILE_SUMMARY.json. Private evidence remains outside Git.

The evidence retains 1 historical coordinator incident receipt(s), separately from final numerical-cell outcomes. Processing costs sum completed cells; a resume launch's elapsed time is not presented as whole-run time.
