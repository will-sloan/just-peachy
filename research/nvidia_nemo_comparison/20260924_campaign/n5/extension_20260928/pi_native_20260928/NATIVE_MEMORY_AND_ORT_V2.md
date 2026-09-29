# Native memory and ONNX Runtime investigation

The combined application still does not fit the admitted 768 MiB virtual-address limit. Smaller native metadata reservations are now qualified for the delayed D1 recipe, and standalone ReDimNet works and exits normally on the Pi. Neither result establishes an integrated release or proves physical 2 GB RAM is insufficient.

## D1 metadata reservation change

A fresh D1-only runtime reduces model/state and temporary graph-probe metadata arenas from 8 to 2 MiB. It retains all allocation assertions, the 2,048-node scheduler with its 95% guard, eight-entry executable-graph LRU, speaker/FIFO history, weights and kernels. Diagnostic logging reports actual metadata use. The initial V1 build failed because its logging helper referenced a function before declaration; V2 corrects only that logging setup. The failed source/logs remain preserved.

V2 library SHA256: `1639518a4de05caa1cf40feb3c9e4e2672cfe82fde87f79f707b115421cdb020`. Its independently reviewed source diff contains only the three capacity constants and diagnostic logging. The delayed whole recipe (264/1/1/0/264/188) passes the original 44.6954375-second source, resident repeat, reset/empty input, EOF, continuous source/frame mapping and process/model closure. All 4,470 × 8 probabilities match the original generic reference exactly at the unchanged 1e-5 gate. Processing takes 18.090/18.105 seconds, RTF 0.405, with 170.984 MiB peak process RSS.

Maximum observed metadata use is 321,264 bytes in a graph-probe arena; model metadata uses 130,272 bytes. The smaller reservation retains headroom for these observed cases. This is not qualification for other profiles, longer workloads or A2 ASR. Processing time is essentially unchanged. See README_D1_METADATA2_V2.md and README_D1_METADATA2_CHECKS_V1.md for inputs, outputs and run/review instructions.

## Combined application trials

Both trials use a fresh shared-controller derivative, explicit delayed D1 composition/manifest, Sherpa ASR, retained ReDimNet E0 and the same constructed first 12 seconds of saved input. The original app remains active; no microphone, enrollment or accuracy scoring is involved.

| Trial | Actual result | Closure / acceptance |
|---|---|---|
| B01 delayed metadata2 V1 | All three models loaded; native D1 reported out of memory and punctuation also logged an ONNX allocation error | Failed. Application queues and files finalized with 192,000 source/identity samples received, but no probability windows. ONNX Runtime native exit handlers stayed alive; only the exact failed unit was stopped. |
| B01 delayed metadata2 V2, telemetry disabled before initialization | Reached graph construction, then native allocation of 39.45 MB failed and aborted | Failed. Exact process is closed, but no clean application finalization or RESULT was produced. Last sampled virtual size 757.734 MiB, RSS 519.422 MiB; the limit stayed at 768 MiB. |

V1's systemd launcher eventually reported success after an explicit stop. That is **not** application success: the preserved RESULT and independent review record failed inference and externally assisted process closure. V2 reached a different allocation failure and cannot qualify the V1 shutdown path as fixed.

A read-only native stack captured V1 inside ONNX Runtime exit handlers, with two remaining ONNX Runtime background threads and open DeveloperTools telemetry database handles. The installed binary exposes ORT_DISABLE_TELEMETRY. Official [ONNX Runtime documentation](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md) and [v1.29.0 release notes](https://github.com/microsoft/onnxruntime/releases/tag/v1.29.0), checked September 29, document setting it before initialization on non-Windows systems. V2 applies it only to the new test process and binds that policy into a new composition manifest. The original app and global environment are unchanged. No telemetry database was read or deleted. Attribution of the entire allocation failure to telemetry is not established.

See README_B01_DELAYED_METADATA2_V1.md and V2.md. The question about a short 1 GiB virtual-cap trial is still unanswered; no higher cap has been used. A larger cap cannot be inferred from low RSS. Further unchanged allocation retries add no evidence.

## Standalone retained ReDimNet E0

The unchanged E0 model ran through ONNX Runtime 1.29.0, CPU provider and one native thread with process-local telemetry disabled before initialization. Original saved prefixes are constructed diagnostics; no profile is enrolled or named.

| Input duration | First / repeat inference | Result |
|---|---:|---|
| 0.5 s | 36.88 / 35.49 ms | Finite 192-dimensional normalized vectors, exact repeat |
| 2 s | 153.75 / 153.83 ms | Same checks pass |
| 12 s | 1.160 / 1.150 s | Same checks pass |

Load time is 0.504 seconds. Peak process RSS across the complete three-duration sequence is 323.922 MiB; per-duration RSS was not separately sampled. This includes the process/runtime, audio and retained allocations, not just model weights. It motivates measuring input-window length and model-buffer lifetime when planning on-demand identity. It does not demonstrate that changing identity windows preserves recognition quality.

Independent review rehashed assets, recomputed vector shape/finite/norm/repeat checks, confirmed session release, natural launcher exit zero and exact owner closure. This qualifies the standalone E0 lifecycle under the tested policy, not combined B01 shutdown. Initial V1 staging used an incorrect deployment-relative path and stopped before admission/execution; V2 resolved the verified content-addressed asset path. Both attempts are preserved. See README_ORT_E0_LIFECYCLE_V2.md.

All measurements are conditional on the original rc5 app remaining active. Full-file combined passage, restart/Stop, UI and ready-to-run packaging, aggregate resource behavior, sustained dense speech and independent real-life validation remain open. Future work must retain one ordered stateful D1 stream and independent captions with Pending/Unknown labels; no silence skips are qualified.
