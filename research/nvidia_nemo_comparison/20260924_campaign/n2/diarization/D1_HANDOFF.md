# D1 standalone adapter handoff

## Implemented and actually run

`prototype/vendor/edge_speech_pipeline/nemotron_diarization.py` is a real stateful Windows native adapter for the exact official Nemotron 3 Q8 artifact. It calls the official standalone diarization C ABI; no default ASR/TTS model or full-file offline diarization is involved. The adapter preserves eight model slots through ordinary turns, emits simultaneous activity as multiple channels, exposes actual post-compute availability times, and resets only when explicitly requested for an independent scene/session. It rejects non-finite/stereo input and post-finalization pushes. Teardown and resident-model/new-stream reset are implemented.

All three explicit geometries were executed: 9/4, 6/2 and 3/1 chunk/right-context coarse frames, each with zero left context, 264 FIFO, 264 speaker cache and 222 update period. The nominal buffers are 1.04, 0.64 and 0.32 seconds. Actual first native emission requires 1.046, 0.646 and 0.326 seconds of arrived samples, before compute and caller batching. Exact one-sample-before/at-boundary neural checks passed.

The original native executor hardcoded four threads. `build_native.py` made a separate N2 source/build and changed that graph-call argument to one; its Windows text write also normalized the copied file's LF line endings to CRLF. This is one semantic source change. The complete runtime DLL hashes and original/modified source hash are in `NATIVE_BUILD_RECEIPT.json`. The original N1 build, source, frozen prototype, original model weights, app environment and personal data were not modified by this subtask. No Git commit or push was made by this agent.

Native empty input, repeat finish, constant audio, explicit reset, teardown, malformed input rejection and 1,600-versus-997-sample delivery-partition tests passed. Partition probabilities were bit-identical on the same three-second saved prefix under every profile. The overlap contract fixture preserves two simultaneous slots and is explicitly distinct from neural inference. See `NATIVE_PANEL_RECEIPT.json` and `NATIVE_BOUNDARY_RECEIPT.json`.

## Reference/native comparison

The official `.nemo` counterpart was hash-verified and restored in the separately owned isolated NeMo environment, using pinned NVIDIA-NeMo/Speech revision `cf724ac337d1ebc7d0dda1e23fb80916f52927a5`, CPU PyTorch 2.8.0 and one numerical thread. Its causal diagnostic runner calls `forward_streaming_step` with persistent cache/FIFO; features are recomputed from arrived prefixes only. No future audio, true transcript, speaker reference or full-file model call enters its predictor. Dither is disabled. The adapter remains the deployable route; the reference prefix frontend is a measured diagnostic implementation.

The panel is deliberately small: the first 12 seconds of S45_01_04 O0 under all three profiles, plus the first 24 seconds of the already-fixed S45_04_09 overlap scene on both matched taps under low and ultra profiles. No new acoustic scenes were generated. O0's historical gain is already present; all runtime gain is 1.0.

| Input/profile | Common frames | Probability MAE | Maximum probability difference | Frames with changed active set at 0.5 | Maximum nearest same-slot boundary difference |
|---|---:|---:|---:|---:|---:|
| Isolated O0 / low | 1,200 | 0.00006445 | 0.02285 | 0 | 0 ms |
| Isolated O0 / very low | 1,200 | 0.00006513 | 0.00888 | 0 | 0 ms |
| Isolated O0 / ultra | 1,200 | 0.00008415 | 0.01850 | 0 | 0 ms |
| Overlap O0 / low | 2,400 | 0.00010310 | 0.04481 | 0 | 0 ms |
| Overlap O0 / ultra | 2,400 | 0.00016084 | 0.04353 | 2 | 10 ms |
| Overlap O1 / low | 2,400 | 0.00021245 | 0.04921 | 1 | 10 ms |
| Overlap O1 / ultra | 2,400 | 0.00029394 | 0.05228 | 7 | 70 ms |

These are route differences, not gold DER/JER or calibrated quality claims. The 0.5 threshold was declared before the runs and was not fitted on this panel. Both overlap tap runs produced two active native slots. Argmax can change inside overlap even when the active speaker set agrees; the application must retain multiple channels. Exact metrics, including activity duration, overlap changes, dominant-slot agreement and segment-count denominators, are in `REFERENCE_PARITY_RECEIPT.json`, `REFERENCE_OVERLAP_O0_RECEIPT.json`, and `REFERENCE_OVERLAP_O1_RECEIPT.json`.

Native outputs contain one more centered-STFT endpoint frame than NeMo's valid feature length on these exact-second inputs: 1,201 versus 1,200, or 2,401 versus 2,400. Both original arrays are stored intact; the table compares only shared support and explicitly counts the unpaired tail. Do not clamp the original model timeline or describe all output as exact phonetic timing. Waveform extraction must intersect available real sample support.

## Resources and nominal profile

The native/reference runs in the preceding tables used one graph thread, below-normal process priority and CPU execution. They were accelerated causal file delivery, not source-paced latency tests. Process resource measurements are functional receipts and do not prove an otherwise idle-machine benchmark.

| Native input/profile | Audio seconds | Wall seconds | Sampled process RSS peak |
|---|---:|---:|---:|
| Isolated / low | 12 | 7.01 | 220.7 MiB |
| Isolated / very low | 12 | 10.41 | 227.4 MiB |
| Isolated / ultra | 12 | 19.60 | 244.5 MiB |
| Overlap O0 / low | 24 | 26.89 | 242.9 MiB |
| Overlap O0 / ultra | 24 | 77.32 | 267.2 MiB |
| Overlap O1 / low | 24 | 27.14 | 243.1 MiB |
| Overlap O1 / ultra | 24 | 76.85 | 268.8 MiB |

The reference process occupied about 1.1–1.2 GB RSS on this panel. Model-file size is not total RAM. Neither receipt estimates the full application or CM5 total system usage. Computation grows as the FIFO/cache fills; the initial 12-second result must not be extrapolated as sustained real-time performance. Cold-model load time was not separately measured by this standalone panel.

Use `low_latency` as the provisional nominal engineering profile for the shared controller because it has the lowest measured computation among the declared options and retains distinct overlap slots in this bounded check. Retain `ultra_low_latency` for sensitivity. Final selection still requires full-screen attribution/coverage, returning-speaker and actual queue/visible-caption results; no selection is based solely on aggregate cpWER. The ultra profile's low nominal buffer does not make it a lower-delay CPU application when computation falls behind.

## Separate desktop CUDA route

The same pinned source and CPU-one-thread patch were built with the existing CUDA 12.6.20 toolkit for SM86. CMake required explicit custom-toolkit selection because global Visual Studio CUDA integration was absent; that initial failed attempt remains recorded. Successful compilation took 1,126.2 seconds with two below-normal compiler jobs. `CUDA_BUILD_RECEIPT.json` binds the complete native DLL set, compiler, build/staging script snapshots and existing local cudart/cuBLAS/cuBLASLt dependencies. Their separate NVIDIA CUDA EULA/license hashes are recorded; these DLLs remain private and are not included in Git or a handoff ZIP.

All three profiles then ran the same first 12 seconds of S45_01_04 O0 against the previously saved CPU probabilities, in a separate process bounded to 300 seconds. The process exited 0 in about 4.3 seconds, including loading/hash checks/comparison. It used explicit CUDA device 0: NVIDIA GeForce RTX 3080, driver 610.62. The adapter CPU default remains `gpu=-1`. Native GPU selection throws on missing/failed initialization and never silently retries CPU; CPU-supported graph operators remain allowed with one CPU graph thread.

| Profile | Streaming wall seconds | Probability MAE vs CPU | Maximum probability difference | Changed activity frames / 1,201 | Nearest boundary difference | Process RSS peak |
|---|---:|---:|---:|---:|---:|---:|
| Low | 0.409 | 0.00006598 | 0.03361 | 1 | 10 ms | 661.9 MiB |
| Very low | 0.371 | 0.00004496 | 0.01447 | 1 | 10 ms | 682.3 MiB |
| Ultra | 0.645 | 0.00007952 | 0.01638 | 1 | 10 ms | 714.2 MiB |

Shapes/finiteness matched, and the 0.5 overlap mask did not differ on this short input. Raw arrays and timings remain in `local/n2/diarization/cuda-parity-v1`; `CUDA_PARITY_RECEIPT.json` binds them. Global GPU snapshots after inference showed 2,868–2,884 MiB allocated and 31–41% utilization, including desktop allocations. These snapshots are not process-isolated peak VRAM, a long-session benchmark, or CM5/2 GB qualification. The small route difference is retained rather than rounded to exact parity.

Windows dependency basenames are shared between CPU/CUDA builds. The adapter now rejects a different native runtime directory for the lifetime of a process, even after close or a loader failure. The actual CUDA panel passed three same-directory model loads and rejected a later CPU-directory request after close. Runtime configuration changes must use a separate process.

The new `run_fixed_screen.py` supports all 96 frozen audio-only jobs per selected profile, one resident model per profile, independent-scene reset, 100 ms causal blocks, immutable attempts, complete hash bindings, per-push availability, bounded worker timeouts, checkpoint resume and an OS-owned writer lock. `SCREEN_PROTOCOL_RECEIPT.json` records actual non-neural preparation/resume, changed-contract/tamper rejection, interprocess lock and timeout tests. An authorized first whole-scene smoke completed low latency on S45_01_04 O0: all 715,127 samples/44.6954375 seconds, 4,470 by eight finite probabilities, 448 push/finish events and 62 nonempty updates. Native compute took 1.0043 seconds, total cell processing 1.5469 seconds, and sampled RSS peaked at 669.5 MiB on explicit CUDA 0 with CPU affinity 14. `CUDA_FIXED_RUNNER_SMOKE_RECEIPT.json` binds this actual cell. Its original coordinator ended; the parent campaign coordinator subsequently resumed the same full 288-cell contract at `local/n2/diarization/fixed-cuda-all-v1`. Completion of that parent-owned bulk run is not claimed by this component smoke.

The complete native screen subsequently finished **288/288 cells with zero numerical failures**, 96 per profile. At 195 completed cells, Windows returned transient WinError 5 while replacing `PROGRESS.json`; this coordinator failure is preserved separately from numerical quality. The authorized `resume_native.py` wrapper added only bounded parent-process JSON replacement retries through `n2/io_utils.py`. It preserved an immutable IO amendment and prior-state/error snapshots, retained the original numerical runner/frozen source/admission, verified and skipped all 195 completed results, then ran the remaining 93 cells. All 195 prior result bindings remain identical. `FULL_NATIVE_SCREEN_RECEIPT.json` binds the complete index, unchanged admission, IO amendment/result and historical coordinator error. The final coordinator/model worker ended, and GPU ownership was released. The index's final elapsed field covers the resume launch only; whole-run processing cost must use per-cell resources and retained launch evidence. Quality scoring is owned by the separate evaluator.

## Remaining scope and limits

- The standalone Windows neural route and reference comparison are ACTUALLY_RUN. Shared frontend/controller selection, label-only ASR invariance, source-paced C105/short paragraph regressions and all four integrated D/E combinations are owned by the parent N2 integration, not claimed by this component panel.
- Full 96-cell native probability screening under all three profiles is ACTUALLY_COMPLETED on the separately identified desktop CUDA route. This does not by itself establish gold diarization quality, shared frontend/controller readiness, or CPU portability.
- More than eight physical speakers cannot be represented safely. The adapter explicitly reports that overflow cannot be detected from the eight probabilities alone and never recycles slots from evaluator knowledge. Eight stable model-slot IDs are not proof of eight persistent physical identities. Gallery names require independent compatible embeddings and contradiction/rejection handling.
- Long-session cache compression and memory behavior beyond these prefixes are NOT_TESTED. Native raw-probability compaction needs a safe silence gap, so a strict end-to-end memory bound is not established.
- ARM64 build, CM5 performance, total 2 GB system admission and physical microphone/USB/telemetry are NOT_TESTED. None of those hardware paths was opened or enumerated. Desktop CUDA performance is measured only on the separately identified short panel above.
- The first reference launch FAILED before model inference because psutil was absent. The environment owner installed pinned psutil 6.1.1; the subsequent run completed. The failed log remains `local/n2/diarization/reference-v1.log` and the successful log is `reference-v1-attempt2.log`.

## Integration and evidence paths

Construct `NemotronDiarizer(model_path, library_path, profile='low_latency', session_id=..., expected_library_sha256=..., gpu=-1)`. The optional nonnegative GPU index explicitly selects the CUDA route. `push(audio)` returns a `DiarizationUpdate`; raw probabilities are `[new_frames,8]`, `frame_start` is global within the session, and `available_at_monotonic` is actual completion time. `finish()` returns the final increment. `reset(session_id=...)` creates a new stream on resident weights. `close()` releases native handles. No ASR words or names are accepted by this adapter.

For cache/release binding, include the full `NATIVE_BUILD_RECEIPT.json` or its `runtime_files` hash map. The C ABI DLL hash alone does not bind the sibling neural implementation/ggml libraries. The API manifest also binds model revision/hash, profile, feature geometry and library identity.

Native DLL: `G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\native-cpu1\build\bin\Release\nemo_speech_asr_c.dll`.

Private evidence parent: `G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization`, with `panel-v1`, `reference-v1`, `overlap-o0-v1`, `overlap-o1-v1`, `reference-overlap-o0-v1` and `reference-overlap-o1-v1` subdirectories. Each has an immutable completed receipt, probability arrays and exact runner source snapshot; the native runs also snapshot the adapter. Redacted receipts bind local paths and SHA256. No raw audio was copied. Large checkpoint/build payloads remain outside Git.

All PowerShell and Command Prompt/Anaconda commands, inputs and outputs are in `README.md` and `prototype/vendor/edge_speech_pipeline/README_N2_NEMOTRON.md`. Stop only the owned process when interrupting; use a fresh output directory to repeat. This subtask has no live worker, scheduled job, GPU owner, Git commit or push to clean up.
