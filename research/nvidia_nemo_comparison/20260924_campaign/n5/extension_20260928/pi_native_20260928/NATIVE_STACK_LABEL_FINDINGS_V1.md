# Native thread stacks, caption-label lineage and retained-E0 failure

September 29, 2026 08:02 UTC. These are native saved-file functional/resource and stored presentation checks. Original rc5 remained active. No new accuracy metric, capture, playback, enrollment or production installation occurred. Read CHECK_SUMMARY_V9.json and preserve all earlier results.

## Process-startup stack change

The earlier Python thread-size setting did not change the default stack reservation for native-created threads. A fresh process receives systemd `LimitSTACK=1048576` before Python starts. The harness checks both soft/hard RLIMIT_STACK and the glibc default pthread stack at 1 MiB. The existing Python setter remains. This is process-local; OS defaults, the original app and the hard 768 MiB virtual-address cap are unchanged. It may be unsuitable for other code or deeper stacks; qualification is limited to the executed path.

The config-only `shared-app-native-stack-v1` retains application pipeline SHA6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491 and the previously qualified delayed D1 LRU1 runtime. Early Stop retained128960samples/807nativeframes and drained in1.698s. Same-process full restart retained all715127source/ASR/D1samples and4470x8 probabilities exactly equal to the original delayed reference at unchanged1e-5. Source/session origins, zero E0 loads/calls, one Sherpa load, learned punctuation, complete application/consumer/archive drainage and natural process exit pass independent review.

Sampled virtual peak fell from765.3125MiB in the preceding check to738.203125MiB, increasing headroom from2.6875MiB to29.796875MiB. Physical peakRSS498.03125MiB is about unchanged; no RSS or inference-speed improvement is claimed. These sequential observations with the original app active are not controlled repeated memory benchmarks or long-run safety evidence. First full-restart text5.643s includes source silence; first probabilities25.488s and EOFdrain11.608s. ASR and D1 costs overlap and must not be summed as elapsed pipeline time.

Execution and independent review commands: README_B05_NATIVE_STACK_V1.md and README_B05_NATIVE_STACK_REVIEW_V1.md. Private `b05-native-stack-v1-evidence/REVIEW.json` qualifies only the stated Stop/restart scope.

## Anonymous caption-label data

Reader V1 incorrectly compared upstream hypothesis token IDs with presentation span IDs. Its failed attempt is retained in LABEL_READER_V1_FAILURE/DIAGNOSTIC receipts. Reader V2 reconstructs stable presentation IDs from the successive raw ASR text revisions, checks labels against the exact targeted revision and session, verifies raw span text and histories, and rejects any personal profile/name evidence. This changes the reader, not the application or model.

Both stored sessions pass: early Stop has9text publications/9label revisions; full restart has41text publications/31label revisions. Full-restart labels comprise20Speaker1,6Unknown,5Speaker2 revisions. First actual label revision arrives25.536s after source start, following first probabilities; captions had already appeared. The accumulated draft includes both sessions by design:40rows and51checked native-label history entries. Counts are event/row structure, not recognized-speaker accuracy or word counts. Timing remains revision-window timing, not phonetic word alignment.

README_B05_LABELS_V1.md preserves the failed reader; README_B05_LABELS_V2.md runs the successful read-only reader. Private LABEL_REVIEW_V2.json explicitly does not qualify actual widgets or speaker-assignment quality. Read-only target inspection found no Xvfb/xvfb-run. No visible Xwayland/desktop session was used for tests, and no display dependency was downloaded.

## Retained ReDimNet B01 is still blocked

The initial native-stack dispatcher V1 failed before admission because it selected a nonexistent short-source filename. It created no numerical owner; preserve its partial staging and failure receipt. V2 correctly binds the existing `prefix12.wav`, using a fresh retained-E0 `open_with_names` configuration, empty research gallery, the qualified delayed LRU1 runtime, 1 MiB startup stacks and the unchanged 768 MiB cap.

The fresh trial produced13text publications but zero D1 probability frames. Its journal records `ASR lane failed: std::bad_alloc`; a terminal native assertion failed to allocate2MiB. Sampled virtual size reached767.90625MiB, with observed VmPeak767.953125MiB and sampledRSS517.625MiB. These samples do not identify the exact transient peak or prove a single cause. There is no RESULT, clean application-finalization receipt or qualified source coverage. Systemd records SIGABRT; the exact PID/boot/start identity is closed. Do not treat closed OS ownership as a clean application shutdown or working mode.

Read README_B01_NATIVE_STACK_V1/V2.md and README_B01_NATIVE_STACK_FAILURE_V1.md. The independent private failure review preserves all bindings. This result does not qualify retained-E0 B01, fix the earlier ORT exit-handler path, or authorize a larger cap. The previously asked 1 GiB trial remains unanswered and was not run.

## Next work and closure

Prioritize an explicit anonymous experimental launch path plus actual native widget/control and save/reopen/delete coverage without desktop takeover. A prepared launcher is not a qualified GUI mode. Retained-E0 B01 remains separate; investigate justified simultaneous buffer/model lifetimes or the pending bounded-cap decision, not unchanged failed variants. Do not reuse D1-only memory bounds for A2. Preserve the one ordered D1 stream, immediate captions and Pending/Unknown semantics; no silence was skipped.

At08:02UTC all56owned identities are closed, original rc5/app identities unchanged. Combined private output641846584bytes of1GiB; C/G and target free-space floors pass. Available target RAM1630732288bytes, free disk19934720000bytes,53.45C/throttle0x0. Global swap counters96in/28743out at16KiBpages changed; they are not per-job attribution or evidence of swap-free timing. Private NATIVE_CLOSURE_V9/NATIVE_RESOURCES_V9 retain the fresh census. N4/N5 acceptance, robust sustained behavior, B02 and independent real-life speech remain open.
