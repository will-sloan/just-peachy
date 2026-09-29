# Native Stop/restart and executable-cache repair

Reviewed September 29, 2026 07:05 UTC. The anonymous B05 shared controller now passes early Stop followed by a full-file restart in the same process with an isolated single-entry D1 executable graph cache. This is functional/resource evidence, not a new GUI/release acceptance or speech-quality result.

## Preserved failures and bounded change

The eight-entry-cache V1 run stopped after 129280 samples (8.08 seconds) and drained in 1.807 seconds. Its restarted file failed at 42.34 seconds with native D1 out of memory. V1 retained its early engine in the test harness. V2 removed that strong reference and accumulated only compact progress counters, but still failed at 42.4 seconds, this time with ASR `std::bad_alloc`. Both failures have independent failure/closure receipts and natural exit 1; the cap was not raised. Early Stop closed workers, queues, archives and handles, but neither attempt passed full restart. Releasing a test reference alone did not fix the failure.

The fresh D1 build reduces executable graph LRU capacity from eight to one. It retains the existing eviction implementation, metadata 2 MiB assertions, scheduler 2048 and 95% guard, weights and speaker/FIFO history. This cache stores executable graphs, not speaker memory. Library SHA256: `7db8afef2e37b28c0f9d56690b4c0d5fcd8c85a50fa6034f8e6fb53674ceb45a`. The single source-line change and retained object/runtime ancestry passed independent build review before inference. The lane-preserving A76 library remains unchanged.

## Native results

| Check | Result | Limits |
|---|---|---|
| Delayed D1 original 44.6954375-second file and resident repeat | 715127 samples and 4470x8 probabilities each; exact generic/reference and repeat equality under unchanged 1e-5 gate; reset/EOF/post-finish/model closure pass | Only the tested delayed 264/1/1/0/264/188 recipe; no A2 or other-geometry qualification |
| D1 workload first/repeat | 18.092 / 18.074 seconds, RTF 0.405 / 0.404; peak 172.969 MiB RSS | No speed or RSS improvement claimed versus metadata2/LRU8; original app active |
| B05 early Stop | 129280 samples retained through ASR/D1, 809 actual frames at forced EOF, 1.720 seconds request-to-controller-return; workers/queues/handles/archive drained | Prefix EOF differs from full-file context; no prefix/full reference or accuracy comparison |
| B05 full restart in same process | Full 715127 samples, 4470x8 probabilities in three updates, exact reference difference 0, source offset reset and separate session IDs/epochs; Sherpa loaded once, E0 never loaded | Anonymous session slots only; no personal names |
| Restart availability | First text 5.645 seconds; first D1 probabilities 25.462 seconds; source EOF-to-completed 11.565 seconds | First text includes initial file silence, not per-word delay; D1 probabilities are not named-speaker/UI latency |
| Combined process memory | Peak RSS 497.734 MiB; sampled virtual peak 765.312 MiB under unchanged 768 MiB hard limit | Only 2.688 MiB virtual headroom: not a robust memory fit or endurance result |
| Combined closure | Zero inference errors, learned punctuation, all application/consumer/archive queues and handles closed, natural exit 0 and exact owner closed | Two explicit terminal punctuation heuristics on full restart; no silent model fallback |

Restart D1 call work was 18.825 seconds and ASR accept/finish 6.238 seconds. These overlap and must not be summed as elapsed pipeline time. The final controller draft contains both sessions' rows by design (40 cumulative including 9 from early Stop); that count is not a sentence/accuracy measure or proof of GUI rendering. The reader checks session identities and source/frame origins in their separate journals. The old engine's weak reference was dead by restart completion; it was not forced through garbage collection.

The application code is identical to the previous full anonymous source: n2_pipeline SHA6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491. Only its copied backend catalog binds the new runtime; manifest `sha256:1c265638ac1033dfbc3e10ef48817cbe4302d0c707dc41c59b8105a47cb7c7b5`. Existing sources and failures remain immutable. Private `b05-stop-restart-lru1-v1-evidence/REVIEW.json` contains the independent scoped acceptance; this does not promote a release profile.

## Next work and boundaries

Prioritize memory headroom, actual caption/anonymous-label presentation and shared UI/control validation before a ready-to-run GUI release. Retained-E0 B01 remains a separate allocation failure and still lacks approval for the previously requested short 1 GiB virtual-cap trial; this work did not raise that cap or qualify naming. Do not rerun passed component/Stop checks unchanged. Longer dense-speech and 30/60-minute runs need fresh resource/time admission. All saved audio remains intact and no new ASR/WER/DER scores, capture, playback or real-life accuracy claims were made.

At closure all 54 owned identities were closed; original rc5/app identities unchanged. Combined private output was 612532847 bytes of 1 GiB. Target temperature 55.1 C, throttle 0x0; kernel-wide swap counters 48 in / 27125 out at 16 KiB pages are contextual, not per-job or swap-free evidence. N4's actual panel and full N5 release remain incomplete.

## Run and review instructions

See README_B05_STOP_RESTART_V1.md and V2 for preserved failing protocols; README_B05_RESTART_FAILURE_V1.md for V2 failure review; README_D1_LRU1_V1.md and README_D1_LRU1_CHECKS_V1.md for build and component gates; README_B05_STOP_RESTART_LRU1_V1.md and README_B05_STOP_RESTART_LRU1_REVIEW_V1.md for successful collection and independent review. Each includes purpose, immutable inputs/outputs and PowerShell/CMD/Anaconda instructions. These run IDs are closed: subsequent work requires fresh paths/admissions and must not overwrite them.
