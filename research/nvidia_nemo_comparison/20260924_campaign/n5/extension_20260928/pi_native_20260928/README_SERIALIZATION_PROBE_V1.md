# Retained D1 packet serialization and scheduling probe V1

Purpose: diagnose the concrete quiet-input overflow near the first large D1 publication without capture or model inference. Replay the existing2112x8 first packet through the actual engine event-writer factory and actual SessionStore archive.event path. Three packet copies per variant are diagnostic repetitions, not a new source stream. A one-second idle control and same-process1ms Python thread plus separate-process1ms timing peer measure scheduling gaps. Per-phase cgroup cpu.stat deltas retain throttling observations; probes themselves add overhead. Thread/peer differences suggest candidates, not proof of GIL ownership or the earlier live fault cause.

Inputs: source-bound b01-quiet-artifact-v1 prototype and compact journal; strict decoder; fresh WINDOW_V5 host/target census. The original variant uses existing json.dumps/deepcopy/async writers. An unintegrated iterencode candidate changes producer, archive event encoding and compact sink encoding only inside the diagnostic process, retaining encoder options. All retained packet fields/probabilities must roundtrip exactly, inputs remain unchanged. No application source is edited. No microphone, GUI, enrollment or playback. No model libraries loaded or weights copied.

Outputs: fresh serialization-probe-v1, exact admissions/owners/unit envelope, bounded THREAD_TIMES/PEER_TIMES, idle/original/candidate phase timestamps and cgroup deltas, per-call encode/enqueue/archive/drain costs, two journals per variant and independently checked closure/exact packet contents. Keep raw probabilities private. The yielding candidate is not integrated/qualified for live use. Latency observations do not equal speech quality or fixed capture.

Bounds:CPU2/3,total200%,one model thread setting (no models),768MiB hard virtual,1MiB stacks,64tasks,300second service/290alarm/10second stop,8MiBfile; fresh850MiB RAM/5GiBdisk.32MiB combined allowance16target+16host. Peer process128MiB virtual,45second deadline; at most20000timestamps per probe. It inherits unit CPU/task limits, records exact owner and must close. No unlimited output. Baseline/OS/config remains unchanged. Main probe capacity exhaustion fails its timing evidence; report all counts.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/serialization_probe_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V72.json
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\serialization_probe_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V72.json
```
Use a fresh unused census younger than15minutes; never reuse the run ID. Worker/gate modes are internal. Independent reader must recompute timing-gap summaries from raw ordered timestamps, check cgroup deltas and exact original/candidate journal payloads, all owners/envelope/output bounds/input hashes and natural closure. Numerical D1 gates are unchanged; no inference occurred. No live retry merely because a variant has a smaller probe gap.
