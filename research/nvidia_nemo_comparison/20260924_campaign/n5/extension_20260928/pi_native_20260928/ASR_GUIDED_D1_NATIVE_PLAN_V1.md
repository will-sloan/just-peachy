# ASR-guided diarizer activity: native priority

User clarification September29,2026: prioritize using fast ASR to propose diarizer-active regions, with lenient context such as1second before and1second after detected speech. This is a candidate to measure, not a fixed optimal margin or already qualified speedup.

## Current evidence

The34-method catalogue already specifies G07 short-delay ASR assistance, G08 longer-delay assistance and G09 cue union. Existing G01–G03 Windows shadow observations do not qualify ASR gating on native CM5. Native Sherpa saved-file functional timing and the functioning B01 pipeline are reusable foundations. No applied silence-skipping method or native ASR-guided speedup is qualified. These new priorities do not change frozen runs or either user preview.

## First bounded native experiment

Keep ASR running on every source sample, captions independent, and one ordered stateful D1 lane. In a fresh B01 derivative log ASR partial/final positive cues, their source intervals and the actual time each cue became available. Keep original source pacing. For an ASR-supported interval [a,b], propose protection [max(0,a-1),b+1]; merge touching/overlapping intervals and conservatively round to the runtime's supported whole chunks. Protect undecided audio while waiting. ASR revision-window timestamps are not phonetic alignments; count that uncertainty explicitly.

A bounded audio buffer must retain the pre-roll plus the admitted cue-wait horizon. Late ASR output cannot retroactively recover audio already discarded. Report cue lateness, necessary lookback, buffer memory, added speaker-label delay, revision changes and late-cue rescues. A1second margin alone is insufficient if cue publication arrives later than the retained buffer. At expiry/overflow or missing cues, retain audio for the first candidate rather than silently skip. Captions should not wait for this speaker decision.

Start in **shadow mode**: every sample still runs through D1; only proposed keep/skip intervals are logged. This measures feasibility and policy cost, not saved inference time. Compare to the exact same ungated composition, resources and1x source pacing. Use the user's proposed±1s as one declared candidate; do not run a Cartesian parameter sweep. Freeze it before held-out real-world tests.

ASR nonempty partial/final output is positive speech evidence. No words is not sufficient silence evidence: missed quiet/short speech, overlap, noise and nonlexical speech still matter to diarization. Use conservative energy or independently checked VAD as positive fallback support, with uncertain/missing cues retaining audio. ASR-only absence gating is a labelled negative control, never the default release policy. End the post-roll after the last supported speech interval, not after an arbitrary last token publication.

## Gate before actual skipping

First validate source-time mapping, quiet/short/overlap retention, returning-speaker history, cache/FIFO context, discontinuity semantics and EOF/Stop flush. D1 processes context as well as newly emitted frames; input selection alone does not prove less native work. Feeding zero audio still executes the model and is not a measured optimization. Do not concatenate disjoint source regions into a false continuous timeline or silently reset speaker history. If no state-preserving skip mechanism qualifies, keep shadow evidence and evaluate an explicit epoch/reset mode separately with its identity consequences visible.

After these gates pass, one bounded applied trial may measure actual model calls/inference CPU, gate/IPC/context overhead, totalRTF, backlog maximum/slope/drain, caption/label latency and corrections, RSS, clocks/temperature/throttle. Match ungated runs and separate ASR/E0/D1 costs. A proposed skip percentage is not a speedup. Dense continuous speech may offer little or no savings; sparse synthetic scenes are conditional diagnostics.

## Real-world validation

Use user-ready consented speech: dense conversation; natural pauses/returning speakers; short and quiet speech; overlap; restaurant babble; steady noise and impacts. Freeze mode/gate settings beforehand and preserve original chronology and speech duty cycle/pause distributions. Saved campaign clips remain functional/resource material, not new ASR/WER or speaker-accuracy scores. No unattended capture/playback or enrollment is authorized. Do not delay a basic usable real-world B01 session for a fully optimized gate.

This document is a specification/prioritization update, not new executable code or a claim that native shadow/applied gating has run. Next implementation must have its own README, fresh source/admission and independent review under the existing resource/output/checkpoint limits.
