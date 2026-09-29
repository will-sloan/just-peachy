# Callback status and journal volume: native diagnostic preparation

September 29, 2026, 18:27 UTC. This adds a correction and narrow model-free evidence to V24; historical admissions, failures and reports remain preserved.

## Corrected interpretation of the live failure

The production callback increments its legacy `dropped_frames` counter by the incoming callback size when any nonzero PortAudio status causes an abort. Thus **480 is the rejected callback block size, not a measurement of total upstream audio loss**. Its nominal duration is 10 ms at 48 kHz, but the actual missing duration and exact PortAudio status are unknown. The prior trial did not retain those flags. It still fails continuous-input coverage, with only 339,360 of 420,000 source samples processed by D1 and no successful EOF finalization. Neither this correction nor the memory repair clears that failure.

## What ran this wake

`callback-fault-v2` ran eight native synthetic cases through the actual qualified source callback: unchanged normal samples/counters, input overflow, input underflow, other status flags, full raw ring, oversized callback, priming behavior and unrelated exception propagation. An independent reader returned `PASS_NATIVE_MODEL_FREE_CALLBACK_FAULT_DETAILS_ONLY`; peak RSS was 31 MiB. No stream, microphone, audio file, model or GUI was opened. Exact service and dispatch identities closed naturally.

The unintegrated subclass adds a bounded scalar record only on callback abort: rejected block length, status bits/flags and available ADC/current/performance times. It preserves the parent abort and leaves upstream loss explicitly unknown. This is diagnostic preparation, not an integrated fix, real-time overhead qualification or proof of the earlier fault cause. V1 failed on a local payload filename before remote staging/admission; its failure remains preserved. [Run and review instructions](README_CALLBACK_FAULT_V2.md).

A subsequent source/admission audit found a bookkeeping mismatch: the admission says 762 MiB virtual space while the test sets the campaign-authorized 768 MiB. The admission also says 90 seconds stop timeout while systemd uses the stricter 10 seconds. The eight functional results stand, but **dispatch/admission conformity is not qualified**. Low peak RSS does not establish virtual usage below 762 MiB. Preserve both receipts and correct/validate admission generation before any future fresh dispatch; do not rerun unchanged functional cases merely for progress. Private `ADMISSION_AUDIT_V1.json` supplements the narrow case reader.

## Why logging needs a bound

Read-only inspection of the failed retry's main 19,989,354-byte session journal found 150 `s6d_display` events occupying 17,457,272 bytes (87.33%). The largest event was 237,318 bytes. Individually serialized field totals were dominated by `segments` (12,865,237 bytes) and `word_spans` (3,073,308 bytes). Values changed in 148 and 145 of the 150 events respectively: simple identical-snapshot deduplication is insufficient. These field totals describe values, not exact whole-journal attribution.

Repeated full display histories are a concrete output target. Their size alone does not prove callback starvation, disk latency or the cause of `INPUT_STATUS_GAP`. No logging behavior was changed in an application or preserved run.

## Next bounded work

Prepare a fresh, byte-enforced diagnostic writer and compact display-history representation, verifying source/session/span/text/label reconstruction against retained logs without rerunning models. Measure serialization/write cost separately before blaming scheduling. Prepare a bounded, reopenable PCM recording path; no listenable recording from the prior live retry is qualified. Integrate fault details only in a fresh derivative and validate all combined output paths before another live trial. Preserve evidence when a bound is reached and expose truncation/failure explicitly.

At closure V32 all 121 research identities were closed; both leases were free, capture closed and original app/config/install unchanged. Combined output was 1,044,257,860 of 1,073,741,824 bytes, leaving 29,483,964 bytes (28.12 MiB). A new unchanged 32 MiB trial does not fit. No capture/reset authorization remains unused; retention consent persists, and future capture requires current readiness after repairs are reviewable.

Private evidence: `LIVE_GAP_SOURCE_INSPECTION_V1.json`, `LIVE_DISPLAY_VOLUME_INSPECTION_V1.json`, `callback-fault-v1-evidence/PRE_STAGE_FAILURE_V1.json`, `callback-fault-v2-evidence/REVIEW.json`, `NATIVE_CLOSURE_V32.json` and `NATIVE_RESOURCES_V32.json`. Their hashes are bound in CHECK_SUMMARY_V25.json. No real-life accuracy, sustained operation or release acceptance is claimed.
