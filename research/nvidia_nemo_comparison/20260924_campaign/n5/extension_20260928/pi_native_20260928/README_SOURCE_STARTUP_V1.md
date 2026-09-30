# Isolated source startup and explicit drainage interface

Purpose: exercise actual XVFLiveSource.start, inventory/endpoint validation, raw-ring allocation, priming, callback/read/FIR and Stop cleanup in a fresh subprocess, then present a controller-facing Start/request_stop/read/finalize interface. This protocol uses fake PortAudio and device-control objects, never opens hardware, and is not an integrated application controller or live B01 repair. It adds startup/interface evidence beyond the previously qualified pre-started callback fixture.

Inputs: immutable b01-quiet-artifact-v1/prototype, original saved WAV prefix, checked transportV2 and source bridgeV1. Fake PortAudio replaces sounddevice before import; actual source.start still calls initialization, real inventory/resolution, explicit ALSA endpoint validation, InputStream constructor/start, route.apply, bounded settling and beam startup. Stream/route/beam implementations only log calls. Hardware lease is a fresh private fixture file. One priming block is discarded before route readiness; accepted raw blocks then enter the unchanged source callback. ADC times are constructed, not physical clocks or acoustic calibration. Real saved audio is used silently and only for function/counts.

The parent receives original startup metadata and reconstructs every LiveBlock field and exact float32 bytes. request_stop is asynchronous; it does not stop consumption. finalize refuses until all accepted IPC blocks and the terminal receipt have been consumed. This avoids treating a Stop request as permission to discard buffered audio. The existing production controller is unchanged and still needs integration. Five cases: Stop with pending audio, empty Stop, callback flag2 after accepted audio, restoration mismatch and startup route failure. Read-before-start, repeated start, premature finalize and post-close operations reject explicitly. Start failures retain source.stop cleanup evidence. No retry/fallback/capture is enabled by this launcher.

Outputs: private source-startup-v1 configuration/metadata, priming/raw counts, constructed converted AUDIO.f32, per-block metadata, original Stop/final Close receipts, fake cleanup order, exact child identities and native service/resource/results. Data remain private and require independent review and hash-verified backup. No ASR, D1/E0, accuracy, physical route restoration, GUI or sustained throughput claim.

Limits: WINDOW_V5 measured target-inclusive32MiB combined reserve (16MiB target plus16MiB host),52GiB payload with2.5GiB retained reservations,5GiB window; fixed32GB Pi and5GiB free reserve. Main hard768MiB virtual, unchanged child128MiB,1MiB stacks,CPU2/3,total200%,Tasks64,one thread,GPUoff;850MiB available before launch. Sampled exact-owner aggregate RSS640MiB/available192MiB stop, not hard aggregate RSS. Main300s/290s alarm/10s stop; child25s, facade startup10s;8MiB per file. Existing research flock and baseline/hardware-lease checks; no OS/config/app changes. Fake child fit does not qualify future PortAudio memory or physical startup timing.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/source_startup_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V91.json
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\source_startup_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V91.json
```

Use a fresh unused census under15minutes. No environment activation/download is needed. Fixed run/receipt roots refuse overwrites; child/worker/gate flags are internal owned entry points. The new modules are imported by this admitted protocol and have no standalone device-launch command. Preserve original evidence and sources, record all failures, review actual limits and exact natural closure before acceptance. Stop before October1 17:47:34UTC.
