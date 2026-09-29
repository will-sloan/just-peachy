# N5 native implementation and field-readiness plan: next 36â€“48 hours

User priority recorded September 29, 2026. Review checkpoint stays October 1, 2026 at 17:47:34 UTC (13:47 Toronto), about 47 hours after this request. This is the implementation target, not a guarantee that every experiment will qualify. Continue hourly in this task and advance useful bounded work each wake; avoid duplicate workers, repeated passed cases or status-only loops when work is feasible. Do not create agents or increase notification frequency.

## Delivery priorities

| Workstream | Concrete implementation | Evidence needed to expose it as usable |
|---|---|---|
| B01 and B05 | Shared GUI, baseline rollback, native Nemotron diarizer with retained ReDimNet or explicit anonymous bypass; reliable live source, bounded journals and listenable recording | Full source passage, correct failure/discontinuity reporting, Stop/drain/restart, save/reopen, actual physical controls and a successful user-ready spoken session |
| Faster D1 modes | Retain measured delayed profile; select one justified intermediate whole recipe; on-demand embeddings; integrate bounded ASR-positive Â±1s/energy shadow and evaluate scheduling | Same-resource native costs, stable state/source time/EOF, dense-speech backlog, visible label delay. Applied omission only after cache/context/returning-speaker/overlap/quiet-speech checks; otherwise retain audio |
| A2 and B02 | Stage existing Nemotron English ASR Q8 model, qualify the native ASR runtime and component first, then integrate as an explicit backend | Load/memory bounds, full source/repeat/reset/EOF, text/sample/time passage, clean shutdown. No D1-only smaller allocator/scheduler assumptions. If simultaneous fit fails, implement clearly labelled sequential Sherpa-first/Nemotron refinement |
| Alternate D1 runtime | Existing NeMo streaming ONNX export interface, explicit NumPy/ORT frontend/cache/FIFO host driver and CPU-provider implementation | Export graph/operator inventory, matched PyTorch/export/ORT numerical and state checks, empty/partial/EOF/repeat, actual ARM64 execution and measured speed. A file export is not a working runtime |
| Field package | Same 480Ã—800 interface/mode semantics, versioned source and backend manifests, offline assets, named launchers, health check/install/activation/rollback, operating guide and Git backup | No network/model download at field startup; clear unavailable modes; original app/data preserved; tested controls, bounded storage, reopenable audio/transcripts, power/thermal/endurance evidence |

B01/B05 remain the first field-test candidates. A2 and the alternate runtime get bounded implementation work during this window even if live capture awaits user readiness. Do not make every optimization a prerequisite for the first useful field build. No silent substitution, personal-name claim from an empty gallery, or untested mode enabled as ready.

## Sequence and checkpoints

1. **First 12 hours:** fix byte-output enforcement, precise callback fault reporting and bounded PCM; stage A2 and determine load/ABI feasibility; inspect the concrete ONNX export contract and freeze frontend/state parity checks. Correct the callback admission metadata mismatch before reuse.
2. **By 24 hours:** target native A2 component passage and an exported D1 graph plus working reference/driver tests where dependencies permit; integrate compact live diagnostics; select the next D1 speed candidate from measured warm-context costs. Record a specific blocker when a branch cannot run.
3. **By 36 hours:** freeze the candidates that actually work; focus on shared GUI controls, standalone launch/rollback and bounded sustained tests. Run bounded autonomous quiet-stream/recording tests under the new authority; do not solicit spoken participation or playback.
4. **Final reserve before the existing checkpoint:** package qualified modes, verify remote refs and offline instructions, update the N5 coverage/field checklist, and report exactly which combinations can be taken out. Stop new dispatch at the checkpoint, safely close owned work and pause the schedule. Do not extend silently.

These are progress checkpoints, not mandatory idle periods. One admitted numerical job at a time, with useful independent preparation while it runs. No Cartesian sweep. Actual 30/60-minute endurance requires its own time/output/resource admission and cannot be inferred from a logical simulated hour.

## Alignment with the original N5 specification

| Original N5 requirement | This continuation's acceptance path |
|---|---|
| Â§1 one source/front end, exact backend manifests, equal modes/capabilities | Preserve shared controls, Pending/Unknown, raw/formatted history, fonts/paragraph behavior and backend failure visibility. Bind exact source, preprocessing, gain, model, runtime, precision, buffers and gallery format. Reuse valid Windows evidence; do not substitute it for native GUI evidence. |
| Â§2 real ARM64 adapters and honest status | Native A2/D1/ORT must actually run. Mark SOURCE_PREPARED, component-tested, native integrated, live-tested and BLOCKED_RUNTIME separately. An emulated/short pass is not a complete Pi release. |
| Â§3 repeatable installation and rollback | Keep original rc5 as control, version new software, share immutable assets, keep personal data outside replaceable code, preserve vector compatibility, bounded eMMC logs/history. Use the now-verified I2S/I2C route rather than the original unverified USB assumption. GPIO/camera/IMU capabilities stay explicitly unavailable unless separately verified. |
| Â§4 backup/provenance | Reviewed small code/docs, pinned manifests/build steps/licenses, remote-ref verification; no private recordings, transcripts, vectors, credentials or model weights in Git. |
| Â§5 guides/coverage/closure | Maintain START_HERE/mode/backend/install/rollback guidance and compact handoff; state N4 panel gaps, remaining GUI/hardware gates and real-world test instructions. No release acceptance inferred from a terminal PASS. |

Later user authorization supersedes the original offline/no-hardware restriction; it does not erase original tests, failures or admissions. N1â€“N3 offline acceptance and incomplete N4/N5 remain accurately labelled.

## Resource decision and capture readiness

The user explicitly authorized adjusting allowances for good Pi operation. WINDOW_V2.json raises combined existing-plus-new host/target output from 1 to **3 GiB**, retaining the original 50 GiB payload ceiling/reservations and C/G free-space floors. Old evidence and V1 bounds remain immutable. New native admissions must use V2 accounting, include target bytes and enforce their own concrete output/time/resource bounds.

Keep two admitted CPU cores and one native model thread initially. Default virtual cap remains 768 MiB; a separately admitted isolated A2 component may try 1 GiB with at least 1.25 GiB available first, while observing the 2 GiB system, original app, swap and thermals. Do not assume this means B02 fits or remove guards. Reuse local assets and existing export environment; no new downloads are currently needed. If a different allowance is justified, record the concrete decision and fresh measured admission before execution.

Both previous spoken readiness authorizations are fulfilled. The latest user instruction now permits autonomous quiet recording without questions; read AUTONOMOUS_QUIET_WORK_V1.md. No user playback or spoken participation is expected. Genuine speech/noise quality evaluation remains a separate future scope, requiring appropriate material: quiet/short/dense speech, pauses/returning speakers, overlap, babble, steady noise and impacts. Preserve original chronology, freeze settings and compare matched controls. Saved/constructed audio remains functional/resource evidence, not new WER/DER or independent real-world quality.

## Concrete runtime inventory from this request

The original app is unchanged, no research units or owners are active and capture is closed. Pi has ONNX Runtime and sherpa-onnx, but no installed torch/onnx/NeMo in the active application environment. The existing host `local/n2/nemo-py312/Scripts/python.exe` does have torch, onnx, ORT and NeMo; any use is export preparation for native deployment, CPU-only within host admission.

Existing pinned A2 Q8 model is **699,872,960 bytes** (SHA256 d9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d). The D1 reference NeMo checkpoint is 198,676,480 bytes. The A2 full NeMo checkpoint is 2,473,041,920 bytes and is not scheduled for copying to the Pi. No model has been downloaded for this request.

Pinned NeMo `sortformer_diar_models.py` exposes streaming_export and six inputs: chunk features/lengths, speaker cache/lengths and FIFO/lengths. Outputs are combined probabilities plus new pre-encoded embeddings/lengths. This does **not** include a complete waveform frontend or host streaming-state update loop. The `chunk` docstring's waveform wording is insufficient: the input-example code constructs feature-frame tensors. Build/verify the feature contract and speaker-cache/FIFO update logic explicitly, including empty FIFO and tail behavior. Existing native Q8 versus newly exported precision is a separate comparison from same-precision ORT/PyTorch parity; do not weaken the native kernel tolerance after observing results.
