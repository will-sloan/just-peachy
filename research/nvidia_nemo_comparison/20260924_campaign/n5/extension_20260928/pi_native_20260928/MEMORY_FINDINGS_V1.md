# Native memory investigation, September29

This report distinguishes virtual-address fit, physical RSS, functional passage and sustained throughput. All candidates retain the hard768MiB RLIMIT_AS, CPUs2/3,totalCPU200%,one native thread/model and current rc5 app. Saved input is functional/resource evidence only. No capture, playback, ASR/WER quality scoring, download or enrollment occurred.

| Trial | Actual finding | Interpretation |
|---|---|---|
| B01 V4 | Still failed thread creation; cleanup passed | Harness read-back reset the requested stack size. This is not evidence against smaller stacks. |
| Model-free pthread inspection | Default8MiB; setter-only1MiB; setter followed by no-argument read8MiB | Direct native stack measurements on this Pi/Python; fixed subsequent harness. |
| B01 V5 | Passed thread creation, then native64MiB allocation abort | No terminal application result/finalization; exact owner is closed. |
| D1 V11 | Scheduler8192→2048 retained exact full/repeat/reference output;269.711/270.112s,226.78MiB peak RSS | D1-only allocation change, not a throughput gain. Original95% guard retained. |
| B01 V6 | Scheduler2048 still hit64MiB allocation before scheduler initialization | Last sampled VmSize705.75MiB/RSS432.64MiB,20threads; no finalization. |
| B01 V7 | One glibc arena reduced initial address reservation, but next64MiB request still aborted | After-start VmSize655.94MiB; later724.36MiB,20threads. Low RSS does not establish address-space headroom. |

A fresh D1-only native session build reduces its temporary/buffer-type metadata defaults and graph probe arenas from64MiB to8MiB. Actual model weights, tensor buffers, computation and all allocation/overflow checks remain unchanged. Its V12 full-source/repeat conformance passed exact reference and repeat equality;269.603/270.440seconds,264.953MiB peak RSS. This is not an RSS or throughput improvement. Combined V8 reached model setup then aborted requesting8MiB. V9 kept those models and tried process-local128KiB mmap/trim thresholds; it also aborted. Last V9 sampled VmSize766.891MiB and RSS512.469MiB,20threads. Neither produced application finalization. These staged memory candidates are not accepted new Pi releases.

Whole native streaming and delayed recipes have also been prepared in an isolated adapter (native-profiles-v1, SHA bf4bbe5746e9797ac72b04b6031ff41ee1c87331d67910d7ba1a9fc8f94c6845), preserving old profiles. They are SOURCE_PREPARED_NOT_EXECUTED. Neither synthetic silence savings nor smaller metadata allocations qualifies real-time performance. The current low_latency geometry still costs roughly6seconds per input second on this full saved source.

Private evidence: b01-v4-dispatch2-evidence, b01-v5/v6/v7-evidence, MEMORY_TRIAL_CLOSURE_V1/V2, THREAD_STACK_INSPECT_V1, D1_SCHEDULER_REVIEW_V11 and current native run directories. Old launchers, failed attempts and all probability arrays remain private/preserved. New executable paths have versioned READMEs with PowerShell/CMD/Anaconda and native commands. No working-profile count is increased by source preparation or a component-only pass.

A bounded1GiB virtual-address trial is awaiting a user decision; it has not been admitted or run. Proposed pre-dispatch RAM floor is1.25GiB, with unchanged180seconds,CPUs2/3 and original app. Existing768MiB limits continue until an explicit reply. All current owners are independently closed; no new integrated profile is accepted.
