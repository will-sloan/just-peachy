# Optional Pyannote primary / continuous delayed-D1 refinement

The actual build10 first trial completed primary Pyannote/TitaNet/ASR with fallback, but the optional D1 child stopped after 2,880 samples with zero output frames. Empty warm-up acknowledgements filled the eight-entry label queue. This reviewed derivative enqueues only nonempty activity masks; all source/frame acknowledgement checks and the eight-real-batch bound remain. Its native combined result is pending. No combined native admission is claimed. The GUI defaults off and stays unavailable until an exact reviewed combined receipt exists. Frozen07 and older releases remain unchanged. This mode is separate from the functional single-D1 late-label path and the older unavailable `provisional_correction` flag.

Purpose: publish primary Pyannote/embedding/ASR text immediately, then revise existing speaker labels using one continuous anonymous CurrentDelayed D1 child. The child loads no ASR or identity encoder. Primary labels remain when refinement is late, ambiguous, disabled or beyond its revision window. Pyannote anonymous still uses ReDimNet continuity; anonymous D1 skips embedding.

## Inputs, outputs and lifecycle

| Module | Inputs | Outputs |
|---|---|---|
| `optional_refiner_protocol.py` | Private socket, bounded messages | Length-framed IPC, maximum65536 bytes; no pickle |
| `optional_refiner_labels.py` | Continuous D1 masks, exact source samples and S7 rows | Existing span/text-revision-targeted label patches; no new text/caption/name |
| `optional_refiner_admission.py` | Reviewed measured v2 proof, exact selection/policy/operational pins | Experimental reuse admission or pre-model rejection |
| `optional_refiner_dispatch.py` | Exact release authorization, selection and request | Separate measured or finite qualification options; GUI eligibility |
| `optional_refiner_qualification.py` | Actual unit/boot/owner/allocation and separately reviewed finite permit | One-use claim and exact execution receipt; never production approval |
| `optional_refiner_resources.py` | Actual owning cgroup | Cached1Hz whole-unit RSS/PSS/VM/swap/CPU and system available RAM, bounded to2MiB |
| `optional_refiner.py` | Parent-owned committed spool/journal and verified options | Single child supervision, asynchronous reads, bounded label handoff and visible fallback |
| `optional_refiner_worker.py` | Inherited private socket under resource limits | Continuous D1 masks; exact owner/source/frame/hash/EOF/model-close receipts |

The parent alone reads active spool segments under their mutex. Each sequential READ is at most3200 samples/12800float32 bytes; no recording-sized copy, unsynchronized `.part` inference, source restart or gap is allowed. IPC activity queue is8 nonempty batches and diagnostics32 records. Empty native updates still validate the exact source/frame clock and advance the received-source watermark, but do not allocate a label batch. Genuine activity batches retain the same overflow fallback; no samples or nonempty masks are discarded by this repair. The label bridge removes conflicting primary anchors, maps independent D1 slots through exact sample-interval overlap and abstains on ties/overlap. Its own patches cannot become primary evidence. An unchanged primary track may retain its genuine name; a changed track receives only the primary anonymous identity. Observation spans are never relabeled as acoustic word alignment.

`worker.worker_options` dispatches pre-model admission, then `InstalledSession._validate_optional_refiner` independently validates it. `attach_optional_refiner` runs after `engine.begin()`. Primary polling never waits for native inference, joins a child, or reads audio. The supervisor/child handles model work and journal RPC. Stop, lag, memory, output or protocol failures drop optional work only, retaining primary audio and labels. No child restart is permitted. Natural source EOF allows finite child drain after primary text completes, without publishing to a closed presentation trace. Explicit Stop skips that drain.

The child sets CPU2/3, retained768MiB AS for first qualification,1MiB stack,512KiB per-file log and a finite lifetime, writes its owner before project imports, verifies the shared200%/Tasks64 unit and uses parent-death SIGKILL. Parent termination/kill/reap is exact-PID-owned. Closure distinguishes a native model close from dead-process closure after kill. Both `child_dead` and `supervisor_thread_closed` must be true before ownership is released.

Output allowance is at least4MiB plus independent mirror reservation:512KiB native log,2MiB whole-unit samples,1MiB hash-addressed alignment proofs and bounded owner/closure files. Overflow visibly disables refinement. No full probability array is persisted here; its native workspace remains policy-bounded. CLOSURE separates `sent_samples` (RPC delivery), `processed_samples` (last returned activity) and `returned_frames`.

## Reviewed experimental use

The measured schema is `just-peachy.pyannote-delayed-d1-admission.v2`, status `MEASURED_COMBINED_CM5_2GB_EXPERIMENTAL`. It requires `experimental_only=true`, `sustained_realtime_qualified=false`, and explicit timing/fallback review. No code creates a measured-pass receipt. The release authorization must separately reference it through `optional_refiner_admissions`, with exact selection, policy, native path, SHA256 and canonical selected asset-inventory SHA256. Every operational setting remains pinned. Only four authorization fields are excluded from the operational binding hash; the actual measured raw binding/package hashes remain evidence.

Validation checks real2GB MemTotal, whole-unit RSS/PSS, child RSS/VM, available RAM, primary matched timing/backlog, child source/frame prefix or complete EOF, zero primary sample drops, one source clock, and exact one-boot owner closure/full mirror. Incomplete refinement is eligible only as explicitly reviewed experimental fallback, with the disable reason and exact uncovered source samples. It does not imply quality or sustained operation. Short input under an ordinary300s maximum remains a short experiment; a developer policy requires actual duration coverage. Undefined `maximum_combined_rolling_rtf` is rejected.

Before primary startup, current available RAM must cover measured combined physical peak plus64MiB and the192MiB floor. Before child startup, it must cover measured child physical peak plus at least64MiB and that floor. AS ceilings are separate virtual limits, not physical reservations. Child AS remains256–768MiB and must exceed its measured VM peak. Whole-unit RSS soft-stop is explicitly768–1024MiB, with1Hz sampling; it is a sampled stop guard, not a kernel hardRSS bound. Available RAM below the floor drops the optional child. Larger-device performance is unmeasured.

GUI enables the optional checkbox only for its exact reviewed selection/default policy; Start repeats validation and current-machine admission. A proof for another embedding/source/window/policy cannot enable it. No checkbox or native capture is selected automatically. Normal headless reuse accepts `--optional-d1-refiner --allow-experimental --diarizer pyannote` through the same Manager/worker checks. A first qualification permit is never accepted by this normal path.

## Timing meanings

`combined_paced_eof_wall_seconds` runs from first source origin until primary and required optional drain/closure. It includes source pacing, waits and tail latency; dividing by the one shared audio duration is a paced completion ratio, not compute RTF. Primary and child component compute-wall times remain separate. Whole-cgroup CPU seconds divided by the same measurement wall seconds gives average used cores; dividing again by2 gives utilization of the shared CPU envelope. Never add two copies of the audio denominator or add overlapping component wall times and call that critical-path time.

The first trial outputs primary health/backlog, child returned sample/frame watermarks and disable reasons, whole-unit resource samples, complete/prefix closure and actual timing. There is no invented combined rolling scalar. A review must name its windows and use the actual corresponding source/worker counters. Successful bounded fallback does not prove real-time processing or speaker quality.

## Run / test

See [README_OPTIONAL_QUALIFICATION](README_OPTIONAL_QUALIFICATION.md) for the first/follow-up permit and same-runtime promotion procedure, concrete PowerShell/CMD/Anaconda preparation commands and native worker entrypoint. For host tests, run the registered CPU14/early-owner wrapper in [README_PIPELINES](README_PIPELINES.md#run-the-focused-tests) with `JP_BENCH_TEST_ROOT` set to its private directory and load `test_optional_qualification`, `test_optional_refiner.AdmissionTests`, and `test_optional_refiner.ChildLifecycleTests`. These are synthetic contracts, no native execution.

The changed08 contracts passed20 tests: `G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-08-focused-e985d02dea044b6695fbd0508bf828a0/RESULT.json`. Coverage includes false/missing permits, physical-versus-virtual admission, exact source/selection/policy/asset pins, one-Hz guards, stable primary fallback, bounded child lifecycle and ordinary reviewed experimental reuse. Earlier07 contract receipts are historical implementation evidence, not evidence of the changed08 native path.
