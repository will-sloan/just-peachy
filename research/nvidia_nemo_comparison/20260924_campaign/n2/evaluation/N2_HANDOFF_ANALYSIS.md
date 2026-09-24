# N2 comparison notes — campaign still in progress

The embedding component experiments and all 288 native profile cells are complete. The native coordinator encountered a Windows progress-file replacement failure after 195 cells, then resumed the remaining 93 with unchanged source/admission/cache. All 288 numerical cells scored successfully and all 96 audio cells match across the three profiles. The original partial snapshot and coordinator incident remain preserved. The four application screens and final candidate decision remain pending. This document is an evidence handoff, not a campaign-completion claim.

The frozen comparison is D0/E0, D1/E0, D0/E1 and D1/E1, with Sherpa ASR and punctuation/casing held fixed. D0 is the existing activity/anonymous-association path; D1 supplies Nemotron native activity with eight fixed slots. E0 is the baseline RedimNet2 embedding path and E1 is TitaNet. Runtime tracking consumes predicted evidence windows and never reference identities, actors, seats or transcripts. E0 and E1 retain separate model/frontend namespaces and galleries. The E1 anonymous-association contrast preserves the D0 operator's original settings; this is not evidence that those settings are calibrated for E1.

Both encoders processed all 1194 identical, hash-bound component windows: 385 clean enrollment clips, 367 clean calibration clips, 120 accepted processed enrollment captures and 322 evaluator-only whole-source-support query windows. Every window met the 0.5-second minimum; each encoder produced 29 gallery conditions. These component query spans differ from the runtime's predicted 0.5–2-second windows. The primary 15-second reference tier is a frozen whole-clip prefix reaching approximately 15 seconds of estimated speech, without clipping, repetition or padding. Clean matched 5/15/30-second diagnostics retain 28 jointly supported identities; unsupported processed duration tiers remain unavailable.

| Primary open component condition | E0 | E1 |
| --- | ---: | ---: |
| Clean-E descriptive query pair EER |4.17% |6.21% |
| Clean-E known-query top1 correct |182/192 |174/192 |
| Processed-E descriptive query pair EER, four position/stream conditions |4.17% each |4.23–5.53% |
| Processed-E known-query top1 correct |184/192 each |179–180/192 |
| Stranger query windows per condition |130 |130 |
| Actual component CPU-thread count |1 |1 |
| Observed component wall time |183.2 s |288.9 s |
| Observed peak process RSS |1182.6 MiB |737.0 MiB |

The primary open roster retains 34 intended and 24 available members. Pairwise EERs describe correlated source pairs and paired taps; they do not supply naming probabilities or an operational threshold. E0's component process also loaded the frozen Pyannote session, and long processed captures affected memory arenas. The memory/time observations are not an isolated comparison of encoder architectures or a 2 GB target qualification. These results favor E0 on the measured component verification diagnostics, but do not establish the best integrated streaming combination.

All operational open-query naming gates reject uncalibrated names. The primary clean open C population has 87 distinct stranger-source clips, below the predeclared 100 minimum. Some smaller clean selected rosters support an empirical C threshold, but no admitted processed C establishes transfer to the actual XVF query domain or to predicted short windows. Closed-roster forced assignments remain explicit unverified assumptions. Runtime reports must retain strangers, unavailable enrollment members, absent enrolled members and Unknown words. No Q score was used to fit a naming threshold.

Each native profile has 96 completed cells in the final comparison. Per tap, 42 cells have complete references, including the empty control; six incomplete ambient cells remain unavailable for full activity DER/JER. Primary activity denominators are 330.28 reference speaker-seconds and 1877.2084 evaluated wall-seconds per tap. Macro JER has 41 nonempty scene denominators.

| Native profile | Tap | Zero-collar approximate DER | Macro scene approximate JER | Consistent / returns | Split identities / merging slots |
| --- | --- | ---: | ---: | ---: | ---: |
| Low |O0 |23.798% |21.243% |57/59 |3/5 |
| Low |O1 |32.318% |21.613% |54/59 |5/6 |
| Very low |O0 |23.834% |20.911% |57/59 |3/4 |
| Very low |O1 |31.585% |21.936% |55/59 |4/4 |
| Ultra low |O0 |24.404% |21.401% |55/59 |5/7 |
| Ultra low |O1 |31.712% |22.708% |55/59 |4/5 |

Each profile/tap condition resolves 161/161 known source turns and 28/28 short turns; none lacks all native activity. Those are coarse activity-intersection diagnostics, with no embedding-evidence claim. Returns that change slots on O0/O1 are 2/5 for low, 2/4 for very low and 4/4 for ultra low; none is unresolved. Each profile/tap has five complete-reference cells with a speaker-count error. The absolute count-error sums are 6/6, 6/6 and 5/6 respectively. There is no eight-slot saturation; the largest simultaneous active-slot count is three. Incomplete scenes retain only known-reference diagnostic scope.

The mandatory 250 ms collar sensitivity retains only 71.08/71.10 reference speaker-seconds per tap, approximately 21.52% of the primary denominator. Low DER becomes 3.827%/40.619%, very-low DER 4.811%/36.203%, and ultra-low DER 6.359%/36.540% on O0/O1. These sensitivity scores cannot replace the primary results. Both variants use estimated 20 ms activity references, not exact phonetic boundaries; neither is comparable to a published phonetic DER benchmark. Native endpoint frames remain stored; scoring intersects their support with actually delivered waveform only.

The empty control S45_12_20 remains a substantive failure: O1 receives 19.16 seconds of false native activity under low, 16.86 seconds under very low, and 16.42 seconds under ultra low, with one active slot. O0 receives zero false native activity in all three. Empty-control false activity contributes to the pooled DER numerator despite having no individual speech denominator. N1's one inserted ASR word on each tap remains a separate failure baseline. The final native report breaks out reference classes to expose this behavior.

Native accelerated wall/audio ratios are approximately 0.0303 for low, 0.0396 for very low, and 0.0608–0.0610 for ultra low on the measured CUDA execution. The shorter profiles take approximately 1.31× and 2.01× the low profile's recorded processing wall time. Activity differences are mixed, with no consistent advantage from the shorter profiles. These native-only results omit ASR, embeddings, naming and GUI work; model loading is amortized. CPU/RSS measurements do not measure isolated GPU memory, CM5/Pi behavior, or total-system 2 GB suitability. Application evidence is still required for the final candidate decision.

Application comparisons require the same 96 audio cells in all four factorial combinations, exact source-bound ASR observations/dispatch/reset sequences, and separate raw/formatted final-text equality. First-visible, first-final and latest shadow caption snapshots retain separate scopes; their timing is modelled from original publications and captured online naming state. Actual Controller output remains authoritative. The older first smoke's observer-caption mismatch remains preserved. Missing cells, missing observer receipts, changed audio/source bindings and invariance failures prevent a successful complete screen summary.

Reproduction and input/output contracts are in README.md. COMPONENT_RESULTS.md and COMPONENT_SUMMARY.json retain the completed component results; native_profiles/NATIVE_PROFILE_SUMMARY.md and its JSON contain the complete native comparison. PROTOCOL_AMENDMENT_01.json binds the zero-collar primary and 250 ms sensitivity declaration. The private preflight keeps its captured input index and original scheduler IDs; the only accepted native alias is N1_BASELINE_ to N2_ with every audio-job field unchanged and the original SCREEN_48 hash verified. Evaluation audit passes 21 tests covering strict aliasing, missing/error denominators, raw endpoint preservation, empty-control false activity, public redaction and ASR source/text invariance. It additionally verifies 2388 stored unit vectors and the frozen manifest/gallery bindings.
