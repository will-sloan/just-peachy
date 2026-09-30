# Isolated source at the application pipeline and Stop boundaries

Purpose: replace the in-process stop-event loop in a fresh process binding with an explicitly admitted isolated source. Stop requests no longer terminate the consumer loop: accepted source/IPC audio continues into the real application MemoryJournal until terminal acknowledgement and child closure. Actual PrototypeEngine.start_xvf construction and Controller._stop_session ownership/shutdown methods are exercised on the Pi with a model-free engine shell. This is a boundary integration test, not complete Controller startup, model/GUI/live/B01 or field-release acceptance.

Inputs: immutable b01-quiet-artifact-v1/prototype, original saved16k WAV prefix, transportV3/facadeV2/bridgeV2. The newly bound IsolatedPipelineSource requires IsolatedLiveConfig rather than silently accepting an old direct-device config. bind_pipeline changes only the loaded process's source factory and restores it after testing; installed and preserved files stay unchanged. Spatial/beam modes are explicitly unavailable because their telemetry has not crossed the process boundary. Controller status reports child ownership; its parent has no PortAudio handle. Future full-controller configuration, models and actual GUI paths need separate integration.

The fake factory invokes the actual source.start and callback/read/FIR/Stop code, but replaces PortAudio/control/beam classes before any hardware access. Its endpoint and lease are private fixtures. It paces96 constructed48k blocks at10ms (each original saved16k sample repeated3times), retaining one priming block. These are simulated timestamps/sample support, not recordings or acoustic calibration. Actual CaptureTimeline remains unchanged. The timing-failure case deliberately advances the constructed stream-start bound10s; accepted transport bytes drain, but journal support is rejected explicitly. No timing gate is relaxed.

Seven cases cover controller Stop while the journal observer holds the source thread, a fresh restart, empty Stop, callback fault after an accepted prefix, route-restoration mismatch, startup failure and impossible timing. Stop-tail cases verify controller STOPPING/engine ownership while blocked at480samples, then release the consumer and require all15,360samples to reach the journal. Callback failure retains960samples and remains failed. Timing failure credits zero journal samples and explicitly reports discarded post-failure transport samples. A model-free engine shell supplies absent model/watcher interfaces; real model acquisition is forbidden. This does not test D1, A2, captions, archive Save/Open or physical widgets.

Outputs: private source-pipeline-v1 code/admission/owner/service receipts, per-case fake route/source/terminal receipts, actual MemoryJournal float bytes, application callback/timing/controller cleanup records, bounded recent64 IPC entries and CASE_RESULT summaries. All input/closed-run hashes bind immutable dependencies. Independent scalar FIR/reference and lifecycle reader required before acceptance; preserve any failures. Startup/terminal errors stay visible in the source, journal and controller; a child closure cannot turn failed audio support into a successful session.

Bounds: no capture, models, playback, enrollment, downloads or private profile edits. WINDOW_V5 target-inclusive32MiB combined output (16MiB target/16MiB backup),52GiB payload including target and2.5GiB reservations,5GiB window. Fixed32GBPi/5GiB free reserve; C50GiB/G75GiB floors. Main768MiB/child256MiB hard virtual,1MiB stacks,CPU2/3,total200%,Tasks64,one numerical thread/GPUoff,initial850MiB RAM. Sampled aggregate640MiB RSS/192MiB available stop is not hard RSS. Main300s/290s alarm/10s service Stop; child90s,facade45s. The10s stop envelope is admitted only for these fake-device cases; actual hardware cleanup uses its separately admitted60s envelope. Source Stop waits for ownership rather than claiming release with a live child. Byte bounds and research/hardware lease checks remain.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/source_pipeline_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V97.json
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\source_pipeline_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V97.json
```

Fresh unused census under15minutes required, CPU14 before host inventory. No environment activation/download. Other modules are internal imported entry points, not independent device launchers. Fixed roots reject overwrites; all failures remain. Backup private evidence with hashes and reviewed code/docs to remote Git. Stop by October1 17:47:34UTC.
