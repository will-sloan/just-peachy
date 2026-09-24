# Reference and metric limits

All 240 accepted scenes remain in the catalogue: 156 complete nonoverlap, 47 complete overlap, 26 incomplete ambient references and 11 empty controls. Both accepted physical taps are retained. The 48-scene metadata-only screen has four scenes per family: 32 complete nonoverlap, 9 complete overlap, 6 incomplete and 1 empty. It includes all three source corpora, five rooms, short handoffs, speaker returns, overlap, nonspeech/music proxies, paired orientation/obstruction contrasts and Upper Loeb. It is a screen, not an unbiased population estimate. The full bank remains required for later retained general combinations.

Full original and normalized text was read and compared to the original source manifest and the full Q occurrence records for all 777 utterance occurrences, not just compact hashes. Original transcript SHA-256 values were also checked. Source audio and full source text stay local. The compact catalogue contains only counts, provenance and limitations.

| Metric | Reference availability and treatment |
| --- | --- |
| Lexical WER/CER, complete nonoverlap | Full normalized text is available. Preserve original words separately; do not normalize model mistakes away. |
| Speaker-conditioned/permutation lexical errors, complete overlap | Full source text and speaker/source assignments exist. Declare concatenation/permutation convention; no exact word alignment is available. |
| Incomplete ambient-reference scenes | Retain the scene and report target-conditioned lexical views only where supported. Omit all-speaker lexical accuracy/DER claims requiring the missing ambient speech truth, with an explicit reason. |
| Empty controls | Report false speech, inserted words and duration/activity measures. WER has no reference-word denominator and is omitted. |
| Diarization/activity | Existing whole-source spans and estimated activity are available with 20 ms grid and tail/onset uncertainty. Treat derived activity scores as approximate. |
| Exact word or phonetic timing | Unavailable in all 777 admitted occurrences (`word_times` is null). Omit exact word/phonetic latency/error metrics. No forced alignment or invented timestamps were created. |
| Punctuation/casing | Original source text contains punctuation in 773 occurrences. It is usable as a source-script diagnostic, not independent conversational punctuation gold; do not claim exact spoken punctuation boundaries. |
| UI/event timing | The source-speed file delivery and actual observed event clocks can measure implementation timing under the declared load. They are not physical microphone/display latency or Pi performance. Concurrent screening is not an isolated resource benchmark. |
| Spatial/seat metrics | Bind only matching saved telemetry and its uncertainty. No scene identities/seat truth may reach inference; missing capabilities remain explicit. |

Prepared O0 is the already-gained historical PCM16 journal (+3 dB exactly once); prepared O1 is unity. File inference consumes both at unity. Raw/processed samples, accepted physical capture identity, gain, exact hashes and original offset mappings are bound. The 800-sample/50 ms convention is already in the scene activity and is not measured hardware latency. No RIR, delay, gain or tap replacement is performed.

Loeb Caf exclusions remain intact. All 30 Upper Loeb scenes remain in the full bank; 12 are in the screen. Historical 180/60 assignments are metadata only. Model output was not read by the screen-selection algorithm.
