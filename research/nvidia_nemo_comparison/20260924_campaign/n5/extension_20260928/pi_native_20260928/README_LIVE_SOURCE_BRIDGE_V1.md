# Real source bridge and fake-callback IPC checks

Purpose: bind the qualified separate-process transport to the real application's source callback/read/stop behavior and retain all accepted raw blocks through Stop. No device startup is enabled by this protocol. It is not yet a controller facade, microphone trial, physical restoration or combined B01 qualification.

Inputs: unchanged source-bound b01-quiet-artifact-v1/prototype, its97tap FIR and detailed callback wrapper; original saved16k PCM16 WAV; qualified isolated_source_transport_v2; fresh WINDOW_V5 host census/target admission. The fixture constructs48k input by repeating saved samples3times, uses real XVFLiveSource callbacks/read/converter/stop and a real DeviceLease on a new research-only lock. Stream/control/route objects are fake; source.start is never called, no sounddevice or SciPy import and no microphone or hardware control occurs. ADC/epoch values are constructed fixtures, not acoustic clocks.

Bridge API accepts an already-started source. It preserves the complete LiveBlock metadata, little-endian float32 bytes, contiguous native/model offsets and epoch. Stop calls the original source Stop, then read continues draining its previously accepted raw ring. The original cached stop receipt is preserved with its pre-drain status; BRIDGE_CLOSE.json separately records post-drain status. Close requires zero pending raw blocks, native/model counts equal to accepted/converted source counters, closed stream, released lease and restoration values RESTORED/ALREADY_RESTORED. LiveGap is an explicit terminal fault with complete status/callback details. No silence skip, model/precision/cache change or hidden fallback.

Nine cases: pre-stopped queued drainage; parent Stop with96raw blocks pending; input flag2 with queued audio; raw-ring overflow; oversized callback; restoration mismatch; cancellation before first read;483native-frame short tail; O1 channel/gain selection. Expected faults remain failures and do not become speech/quality evidence. Normal cases and accepted prefixes must preserve IPC bytes exactly. Independent direct97tap FIR calculation uses the earlier predeclared1e-7 amplitude tolerance, not a relaxed D1 gate; no D1 runs and its1e-5 gate stays unchanged. Verify metadata/native mapping, final zero-tail status, actual Stop cleanup order and private-lease release. Fake restoration only qualifies call ordering and error propagation.

Bounds: same actual main768MiB hard virtual/child128MiB,1MiB stacks,CPU2/3,total200%,Tasks64,main300s/290alarm/10s stop,child25s,8MiBfile. One child at a time,64 outstanding blocks/65536encoded bytes,terminal ACK from V2. This is not an aggregate768MiB memory limit or live-source startup fit. Initial850MiB available/5GiBdisk;32MiB combined output16target+16host and sampled aggregate guard. No change to original app/data/config/OS/swap. Each child writes exact identity and terminal receipts; all natural exits/failures are reviewed.

Outputs: fresh live-source-bridge-v1 admission/owners/unit envelope,per-case raw-setup/config/LiveBlock traces/private constructed AUDIO.f32,original Stop and final Close receipts,cleanup call sequence,child and protocol results. No new microphone recording. Preserve failed attempts and source hashes; backup private files with hashes without removing target originals. These tests do not qualify actual start/readback/routing, pending raw audio during hardware restoration, capture-process RSS with PortAudio, GUI or live model throughput.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_source_bridge_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V79.json
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_source_bridge_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V79.json
```
Use a fresh unused census younger than15minutes. Run ID cannot be reused. Worker/gate/transport child flags are internal and cannot turn this fixture into capture. Review with the independent reader before acceptance.
