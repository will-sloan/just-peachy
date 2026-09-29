# Native Tk, archive controls and simultaneous model fit

September29 09:03UTC. Read CHECK_SUMMARY_V10.json. These are actual native CM5 functional/resource checks with the original rc5 app active, not speech accuracy, an uncontended benchmark, physical display certification or a production release. No microphone, playback, downloads or enrollment occurred.

## Real widgets and archive round trip

The installed Tk can exercise its actual widgets on the existing display connection while the new root stays withdrawn. The harness withdraws before any event/idle mapping, prohibits deiconify and asserts unmapped state. No visible window, desktop focus change, mouse or keyboard input is requested. This avoids requiring a new Xvfb download; it does not simulate screen pixels or touch.

Four immutable attempts are retained. V1 selected the ordinary mode page but anonymous conversation is on Advanced; it closed cleanly with a harness assertion. V2 reached all requested controls, then failed because the baseline ResidentModels does not expose a separate punctuation counter. V3 corrected that no-load check; the independent reader rejected its immediate all-collecting label snapshot. Source inspection established the existing0.2s stabilization/1.2s pending timeout, not a proven application fault. V4 records initial collecting labels and services the real Tk loop for1.372s before final checks. No artificial time override or application change was made; the expected final-label gate remained.

Independent V2 reader passes for all40reopened rows: raw/formatted text, labels, spans, IDs, source intervals and speaker history match the previously qualified final snapshot. Actual Text widget contents match the expected final captions. The UI buttons select the experimental backend and Advanced anonymous mode, pin/save, reopen, cancel deletion, confirm deletion of the copied archive, and return to baseline. Zero ASR/speaker/enhancement loads or streams; no ASR-owned punctuator. Controller, Tk and exact process close naturally. The original10MiB archive remains hash-identical; only the fresh test copy is deleted. PeakRSS121.891MiB.

See README_NATIVE_UI_ARCHIVE_V1/V2/V3/V4.md and README_REVIEW_NATIVE_UI_ARCHIVE_V1/V2.md for immutable commands and failures. Private b05-ui-archive-v4-evidence/REVIEW.json is PASS_NATIVE_WITHDRAWN_WIDGETS_AND_ARCHIVE_ONLY. Stored-data replay is not new inference or measured live GUI latency.

## Tk and the real pipeline together

A separate new integration run adds the actual shared UI event loop to the previously passed B05 Stop/restart protocol. It is justified by Tk's extra memory and concurrent rendering; no unchanged component benchmark was repeated. Fresh shared-app-native-gui-v1 is file-for-file identical to shared-app-native-stack-v1. Runtime/model weights/history/geometry remain unchanged: delayed264/1/1/0/264/188, metadata2MiB, scheduler2048/95%guard, executableLRU1, lane-preserving A76CPU, process-startup1MiBstack and hard768MiBaddress space. These smaller D1 bounds remain recipe-specific, not A2 bounds.

Early Stop retained130880samples/819frames and drained1.734s. Same-process full restart retained715127source/ASR/D1samples and4470x8 probabilities exactly equal to the original delayed reference at unchanged1e-5. Sherpa loads once; E0 stays unloaded. Forty final widget rows pass, with zero Tk callback errors, all application/consumer/archive lanes/handles drained and natural process/Tk closure. One and two explicit terminal punctuation heuristics are retained in the early/full sessions respectively.

PeakRSS508.546875MiB, sampled virtual747.343750MiB, headroom20.656250MiB under the unchanged cap. This short test does not prove robust long-conversation fit. Full-restart first text5.639s includes initial source silence; first D1 probability25.518s; EOF-to-completed11.695s. Concurrent component costs are not added as elapsed time. Withdrawn widgets and a sampled event loop do not qualify physical480x800 layout, scanout/touch or user-perceived latency. B05 is explicitly anonymous, with no persistent personal names.

See README_B05_NATIVE_GUI_V1.md, README_B05_NATIVE_GUI_REVIEW_V1.md and README_NATIVE_UI_DOCUMENTATION_ERRATA_V1.md. The addendum corrects inherited parent/no-GUI prose without changing admission-bound documentation. Independent private b05-native-gui-v1-evidence/REVIEW.json is PASS_B05_WITHDRAWN_TK_STOP_RESTART_ONLY. All source hashes and failed attempts remain preserved. The retained-E0 B01 allocation problem and the earlier combined ORT exit-handler issue remain open; no higher-cap test occurred.

## Next actions and closure

Prepare a guarded user-invoked anonymous saved-file preview based on the now qualified native source; keep original app/data/autostart and explicit no-capture defaults. The Start/Stop/file selection/mode restrictions and fresh resource/admission path need qualification before calling it a delivered ready-to-run mode. A prepared launcher alone is not acceptance. Physical screen/touch, sustained memory/backlog/endurance and real noisy speech require separate evidence. Retained-E0 B01 remains separate and blocked; the previously asked bounded1GiB virtual-cap trial is unanswered. Do not repeat unchanged failures or assume a cap increase.

At09:03UTC all61owned identities are closed, original rc5/PID1013:start569 and1130:start607 unchanged. Combined output681662352bytes of1GiB; C/G/target space floors pass. Target availableRAM1631010816bytes, free19899990016bytes,53.45C/throttle0x0. Global swap120pages in/28743out at16KiBpages is contextual, not per-job attribution or swap-free evidence. NATIVE_CLOSURE_V10/NATIVE_RESOURCES_V10 retain exact identities and counts. N4/N5 completion is not accepted.
