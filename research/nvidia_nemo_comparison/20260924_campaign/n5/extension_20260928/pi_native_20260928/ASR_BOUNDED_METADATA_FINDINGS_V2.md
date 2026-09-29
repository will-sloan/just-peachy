# Bounded ASR-shadow metadata: native model-free evidence

September 29, 2026. Independent review: `PASS_NATIVE_MODEL_FREE_BOUNDED_METADATA_ONLY` in private `asr-bounded-shadow-v2-evidence/REVIEW.json`, bound by CHECK_SUMMARY_V22.json. Execution and review instructions: [README](README_ASR_BOUNDED_SHADOW_V2.md).

The fresh, unintegrated shadow candidate bounds both buffered audio and policy history. It preserves the prior positive-ASR +/-1 second support, energy fallback and causal decision horizon. All audio is retained. No model, microphone or playback ran.

Twelve checks passed on the Pi: seven exact short-policy comparisons with V1, tiny-block pressure, disjoint-cue overflow, a late cue after history retirement, a logical hour of source events, and invalid/closed/discontinuous/fresh-session handling. Overflow makes future decisions retain audio. A positive cue potentially intersecting retired quiet proposals exposes an incomplete audit and keeps future audio. Retired detailed history cannot be reconstructed from the bounded summary; this is deliberately conservative, not exhaustive retrospective validation. The disjoint future-cue flood is adversarial metadata input, not representative ASR output.

Limits are 48,000 float32 audio samples (192,000 payload bytes), 256 pending entries, 128 merged ASR intervals, 128 energy intervals, 512 recent decisions and 32 progress records. Counts and hashes summarize retired records. These collection limits do not define an exact total Python memory limit.

The 60-minute logical trace contained 57,600,000 samples in 180,000 blocks. It ran unpaced in 5.661 seconds, with exact ingress/egress hash correspondence and no skipped samples. The full check process took 6.044 seconds and peaked at 30.5 MiB RSS. This is **not a 60-minute live endurance test, model speedup or real-time qualification**. The independent reader reconstructed the deterministic input hash rather than trusting only the tested module's hash.

Next, replay the previously retained actual cue/progress/audio chronology through this bounded candidate without rerunning models. Adapt the bounded report schema explicitly before any fresh B01 integration. Whole-chunk inference omission, cache/FIFO state, context, source-clock gaps and EOF remain unqualified. Missing ASR cues or successful processing without words still do not prove silence.

The user deferred spoken capture: "Not now; continue without capture." The prepared live B01 trial remains unrun. Wait for the user to signal readiness before asking for current readiness and private diagnostic consent; do not repeat capture prompts on hourly checks.

Closure V24 found all 107 recorded research identities closed, original app/config/install unchanged, capture closed and both leases free. Combined outputs were 971,192,328 of 1,073,741,824 bytes (about 97.8 MiB remaining). Reserve space for the first actual live trial and its review. Global swap observations are contextual, not per-job or swap-free evidence. Existing source and all previous failures remain preserved.
