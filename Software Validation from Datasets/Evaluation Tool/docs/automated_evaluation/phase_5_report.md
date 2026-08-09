# Phase 5 Report: Resource Telemetry and Component Timing

## Outcome

Stage 5 adds scenario resource sampling and component spans without changing inference outputs. Campaign CLI execution remains sequential by default: one scenario subprocess and therefore no simultaneous GPU-heavy scenarios per machine.

The frozen `artifact-registry.v1` remains byte-for-byte unchanged and is still the default reader for legacy campaigns. New campaigns created by the CLI use additive `artifact-registry.v2`, which inherits v1, expands `resource_usage` to `resource-usage.v2`, and registers component spans, resource summary, and availability artifacts. Scenario IDs and Stage 2 hashes are unaffected because worker, machine, output, attempt, and telemetry settings remain outside scenario identity.

## Implemented measurements

- UTC and monotonic timestamps, elapsed time, campaign/scenario/attempt/worker/host/PID;
- recursive process-tree PIDs and active component;
- process/system CPU, process RSS/VMS, system RAM;
- process/system disk counters and scenario-volume free space;
- GPU index/UUID/utilization/memory utilization;
- process-tree VRAM, running peak VRAM, total VRAM;
- temperature, power draw/limit, graphics/memory clocks, and throttling reasons where NVML supports them;
- explicit null values and availability reasons when a provider or sensor is absent;
- configurable sampling interval with a one-second default and gap warnings.

Component spans cover audio loading, augmentation, VAD, segmentation, diarization, ASR model load/inference, embedding model load/extraction, speaker matching, prediction serialization, scoring, plotting, reporting, and total scenario time. High-resolution wall spans use `perf_counter_ns`. CUDA-designated spans use synchronized Torch CUDA events only when CUDA timing is enabled and available.

## Artifact and recovery behavior

Stage 5 publishes through the existing atomic writer and checksum manifest. The scenario registry version is selected from campaign/status/checksum declarations; old v1 campaigns remain readable. A telemetry-enabled legacy attempt is migrated additively to v2 by atomically updating mutable run/status registry declarations and rebuilding checksums. No temporary or unknown resource files are smuggled into a v1 completion result.

Raw coordination files remain in campaign audit storage. Shared artifacts contain no absolute source/model/output paths, credentials, or environment-variable values. Telemetry publication failure preserves inference output and becomes an explicit terminal telemetry failure instead of a false successful result.

## Qualification evidence

- real CPU/process/RAM/disk smoke passed with pinned `psutil`;
- real RTX 3080 NVML sampling returned UUID, utilization, process VRAM, temperature, power, clocks, and throttle state;
- fake CPU/GPU, missing-NVML, process-tree, sampling-gap, peak, nested/overlap, artifact, executor, and prediction-invariance tests passed;
- full repository suite: 459 passed, one CUDA-only smoke skipped, and two pre-existing dependency deprecation warnings;
- GUI validation harness passed across its clean, controlled-noise, AMI, VOiCES, CHiME-6, preview, and missing-prediction exercises;
- Ruff and `git diff --check` passed;
- the CUDA-event smoke is implemented but skipped in the current environment because Torch is `+cpu` and reports no CUDA runtime.

## Remaining gate

CUDA timing is not qualified by this phase on the current interpreter. The existing CPU environment must remain intact. Create the separately pinned CUDA environment defined by the readiness plan, then run the single-job CUDA timing smoke and one real selected pipeline. Do not start standard/large benchmarks, performance model selection, or GPU concurrency qualification until that gate passes.
