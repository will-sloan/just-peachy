# N2 matched speaker embedding component results

Both encoders actually processed the same 1,194 bound saved-waveform windows: 385 clean E, 367 clean C, 120 processed E captures and 322 evaluator-only query spans. Every window met the 0.5-second admission minimum. There were no failed/omitted windows. Each encoder produced 29 model-bound private research galleries; no personal gallery was accessed.

The following primary open-gallery results use 34 intended and 24 available members. Query component windows include both taps and are whole-source-support diagnostics; they are not the runtime's selected 0.5–2 second windows. Scores and margins are uncalibrated for processed query naming. Pairwise EER is descriptive, with correlated pairs.

| Encoder | E domain / position / stream | C pair EER | Q pair EER | Q known top-1 correct /192 | Q stranger windows |
| --- | --- | ---: | ---: | ---: | ---: |
| E0 | clean_source / original / mono16k | 0.38% | 4.17% | 182 | 130 |
| E0 | XVF_processed / R04 / auto_asr_raw | 0.36% | 4.17% | 184 | 130 |
| E0 | XVF_processed / R04 / auto_pp_raw | 0.36% | 4.17% | 184 | 130 |
| E0 | XVF_processed / R12 / auto_asr_raw | 0.36% | 4.17% | 184 | 130 |
| E0 | XVF_processed / R12 / auto_pp_raw | 0.36% | 4.17% | 184 | 130 |
| E1 | clean_source / original / mono16k | 0.59% | 6.21% | 174 | 130 |
| E1 | XVF_processed / R04 / auto_asr_raw | 0.81% | 4.69% | 180 | 130 |
| E1 | XVF_processed / R04 / auto_pp_raw | 0.72% | 4.23% | 179 | 130 |
| E1 | XVF_processed / R12 / auto_asr_raw | 0.71% | 5.21% | 180 | 130 |
| E1 | XVF_processed / R12 / auto_pp_raw | 0.71% | 5.53% | 180 | 130 |

The clean primary open roster had only 87 distinct stranger-source C clips, below the predeclared 100-clip minimum. Its C gate therefore rejects all names. Smaller selected rosters can support a clean-domain empirical C threshold, but clean C does not calibrate processed XVF queries. All operational open naming gates remain `UNCALIBRATED_REJECT_ALL`. Explicit closed-roster names are unverified assumptions, to be evaluated separately in the online observer.

E0 completed in 183.2 seconds and E1 in 288.9 seconds, with one CPU thread each. Their observed peak process RSS was 1182.6 and 737.0 MiB respectively. E0's standard SpeakerModels object also loads the frozen Pyannote session, and long processed E captures enlarge memory arenas. These are component process observations during the campaign, not an isolated architecture benchmark or a 2-GB target qualification.

All clean 5/15/30 matched-population diagnostics, separate processed position/stream results, shortage denominators and source/model hashes are in COMPONENT_SUMMARY.json and the private component results. The observed differences do not establish integrated streaming superiority. Actual D0/D1-selected-window results belong to the common application runner and RuntimeGalleryObserver.
