# Bounded live event and PCM preparation (native, no capture)

Purpose: prepare compact diagnostics and reopenable recordings before another autonomous quiet B01 trial. This is a new model-free native replay of two preserved failed-live journals, not a rerun of inference or a microphone test. It does not fix or explain the old input-status gap by itself. Production application, baseline config, original previews and old evidence remain unchanged.

`bounded_live_artifacts_v1.py` is an unintegrated consumer-thread library. `CompactJournal(path, byte_limit)` retains every event and all source/session/span/raw/formatted/label fields; display payload changes become ordered recursive patches against the previous same-session display, with literal fallback. At most two prior payloads are retained, each limited by the1MiB full-record bound;4096 patch operations/depth24 trigger literal fallback. It rejects writes before the8MiB journal cap (including512-byte footer reserve), closes with an explicit failure footer and raises OutputLimit. It is never called from an audio callback. Serialization and actual write time are separately observed; results do not imply a callback scheduling improvement.

`PCM16Writer(path,max_frames)` writes mono16k little-endian PCM16 with a44-byte WAV header and exact contiguous sample offsets. Bounds are checked before accepting each complete block. Float32 conversion rounds/clips explicitly and counts clipped samples; tests preserve original PCM bytes exactly. At most60seconds can be configured; the replay uses715127frames. `close()` finalizes the header and fsyncs. Frame-limit failure closes the accepted prefix, raises OutputLimit and leaves an explicit metric. Future application integration must journal that failure and stop/report incomplete coverage, never silently continue. Metadata is caller-owned; no success is inferred from a file alone.

Inputs already on Pi: original44.6954375s/16k saved source plus both complete retained event journals from b01-live-trial-alsa-user-20260929T180625Z. All hashes are bound without copying originals. The actual source callback is exercised with fake PortAudio status and no stream/device/control open: normal block plus synthetic overflow, then exact fault details are written/reconstructed. This newly checks the fault-to-journal route and exact corrected768MiB/10s admission; it does not recover the original trial's unknown flags or measure upstream loss. The old762/768MiB mismatch remains preserved.

Outputs: fresh private target live-artifact-replay-v1, two compact journals, reopenable saved-source WAV, small clipping/invalid/quota fixtures, timings, actual live systemd properties/owners and RESULT. A separate independent reader compares every reconstructed event field and reopened PCM byte to originals. It checks explicit byte/record/frame failures, source hashes, natural process closure, actual768MiBvirtual/1MiBstack/CPU2/3/quota200%/Tasks64/300s/stop10s/file8MiB limits, no capture and unchanged baseline. No live recording, playback, speech accuracy, app integration, sustained behavior or release acceptance follows.

Fresh WINDOW_V5 admission reserves64MiB combined (32MiB target outputs/staging plus32MiB host evidence), counts existing target bytes under52GiB total with2.5GiB reservations, preserves5GiB available on the fixed32GBPi and C50/G75GiB. InitialRAM850MiB, sampled available192MiB/RSS640MiB stop, one native thread/GPUoff; noMEMCG/RSS hardlimit claim. Research lease and exact owner/boot checks apply. Worker alarm290s/service300s. The sink checks bytes before writing; the outer directory guard remains sampled. No download, model load or capture.

PowerShell (first obtain a fresh WINDOW_V5 host census; fixed run ID refuses overwrite):
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_artifact_replay_v1.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V59.json
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_artifact_replay_v1.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V59.json
```
Internal --worker/--gate are only for the registered supervisor. After both exact owners close, run the staged independent reader via the same strict SSH from PowerShell, CMD or Anaconda:
```bat
ssh -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local "/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/live-artifact-replay-v1/review_live_artifacts_v1.py"
```
Reader output is REVIEW.json plus scalar statistics/hashes; audio/transcripts stay private. Never replay this completed unchanged case merely to show activity. Subsequent application/capture integration requires a fresh derivative, backup/restoration path, exact authority-bound admission and separate review.
