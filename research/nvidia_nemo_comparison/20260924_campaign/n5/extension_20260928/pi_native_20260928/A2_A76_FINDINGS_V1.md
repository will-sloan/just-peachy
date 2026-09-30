# A2 A76 CPU candidate: faster observations, exact-output failure

September30 2026. Independent review: `REVIEWED_A2_A76_GENERIC_EVENT_MISMATCH_ONLY`, private `a2-a76-full-v1-evidence/REVIEW.json`. The candidate is not accepted as the generic runtime's replacement.

Only three `libggml-cpu.so` aliases changed to the existing lane-preserving A76 library, SHA256 `f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557`. The A2-specific ASR library retained SHA256 `6415fb2a77aa5483bbb91e5ecaf5d58c6c3f9edbfe92575f1ab2389d6064bc1b`,16MiB metadata,8192 scheduler/95% allocation guard and original graph cache. Shared ggml-base/ggml libraries and adapter were identical. The actual loaded CPU mapping points to the fresh candidate directory. No weights were recopied and no D1-specific memory limits were borrowed.

Both complete715127sample streams produced87 events,86 nonempty publications, exact resident-repeat events, EOF idempotence and post-finish rejection. Compared with the retained generic reference, event22 and23 have different intermediate raw text; event52 differs in one word's start/end times. The final event is identical. These zero-based positions describe functional differences, not accuracy scores. The exact canonical-event gate failed unchanged; the handled failure destroyed the recognizer and exited naturally1. It is not an accepted pass merely because the final transcript agrees.

| Runtime observation | First full44.695s file | Resident repeat | RTF first/repeat |
|---|---:|---:|---:|
| Retained generic qualification | 78.542s | 77.096s | 1.757 / 1.725 |
| Unqualified A76 candidate | 63.096s | 61.594s | 1.412 / 1.378 |

The candidate loaded in0.807s; kernel peakRSS966.406MiB. Both runs used the same isolated1536MiB virtual cap, initial1408MiB available RAM requirement,CPU2/3,total200%,one native model thread,1MiB stacks,Tasks64 and600s bound. Baseline rc5 stayed active. These sequential observations show a promising runtime difference, but neither meets real-time processing and this failed candidate is not a qualified speedup. Independent logits parity and the precise source of changed hypotheses/timing remain open.

No memory, log or sampled aggregate-output guard fired. Target output8,235,638bytes including the review was backed up privately with exact hashes; originals remain. All exact worker/gate identities closed, capture stayed closed, both leases were free and baseline install/config hashes remained unchanged. The generic runtime remains the qualified A2 component for subsequent sequential-mode work.

Next: use the generic A2 component in an explicit Sherpa-first, Nemotron-after-stop refinement path with bounded process lifetimes and GUI state. Keep this A76 derivative separate until a justified numerical/hypothesis investigation establishes its scope. No unchanged rerun, new WER/DER scoring or silent runtime substitution. This is not integrated B02, physical GUI, live/endurance, malformed-WAV reader or full N5 acceptance.

Execution/inputs/outputs: [candidate README](README_A2_A76_FULL_V1.md), [independent reader](README_REVIEW_A2_A76_FULL_V1.md). Private transcripts, word records, models and full traces stay outside Git.
