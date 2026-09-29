# A2-specific metadata candidate build

Purpose: create a fresh native ASR candidate after the separately preserved 1GiB/1.25GiB stream-allocation failures. Change only session metadata reservations from64MiB to16MiB, with measurement logging. Retain8192-node scheduler/95% guard, original executable cache, tensor allocation assertions, generic CPU kernels and model mathematics. This does not assume D1's2MiB/2048/LRU1 bounds apply to ASR. A successful build is not A2 numerical/resource qualification.

Inputs: immutable scheduler-native-v1 source bundle, its exact manifest/patched-session hash, retained28ASR objects and static libraries. The builder verifies all retained build inputs before changing only a new session.cpp in a2-memory-build-v1. No original sources, installed app, weights, configuration, OS or swap are changed. No model inference, audio capture/playback or downloads.

`a2_memory_build_v1.py` dispatches and retains the research lease and boot/PID/start identities; `build_a2_metadata_v1.py` compiles session.cpp and relinks the native ASR library. Live systemd properties are saved before compilation. HardAS768MiB, CPU2/3/quota200%, Tasks64,1MiB stack,180s service/10s stop, availableRAM850MiB and disk5GiB minimum. One compiler at a time; compiler children inherit limits. Fresh host/target combined output reserve64MiB under WINDOW_V2, original payload reservations and drive floors. Log/file bounds and sampled memory guard retained from reviewed probe scaffolding; sampled parent RSS is not aggregate compiler RSS enforcement.

PowerShell from campaign worktree:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/a2_memory_build_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V37.json'
```
CMD or Anaconda Prompt, no activation required:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\a2_memory_build_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V37.json
```
Census must come from window_guard_v2.snapshot and be less than15minutes old. Fixed run ID refuses overwrite; retry/change requires a new derivative/admission. Worker/gate/builder entry points are internal to the admitted dispatcher.

Outputs: private target a2-memory-build-v1 admissions, exact owners, LIVE_ENVELOPE, patched session.cpp, output/{session.cpp.o,runtime.a,libnemo_speech_asr.so}, command logs, BUILD_RESULT and DISPATCH_RESULT; compact host preflight/launch receipts. Independently review input hashes, exact patch, all compiler/link exits, ELF dependencies, output hash/bound and natural owner closure. Subsequent inference needs a separate admission and must measure actual metadata use/graph sizes, full-source/repeat/reset/forced-endpoint/EOF and memory. Do not replace a qualified runtime from a build receipt alone.
