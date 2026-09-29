# Native A2 original full-file and resident repeat

Purpose: advance the separately reviewed two-second lifecycle candidate to the original44.6954375-second saved file, nonempty transcription passage, repeat/reset/EOF/destruction. The two-second result produced empty final text and does not qualify speech passage. This is unpaced native component timing/resource evidence, not WER, real-world accuracy, original1x scheduling, forced-endpoint conformance, B02 integration or N5 release.

Inputs: existing pinned A2 Q8 weights, original715127sample16kPCM WAV, unchanged C-ABI adapter and A2 metadata16 library SHA6415fb2a77aa5483bbb91e5ecaf5d58c6c3f9edbfe92575f1ab2389d6064bc1b, generic CPU,8192/95% scheduler guard, original cache, right-context1/160ms native step. No capture/playback/downloads/enrollment or changes to the original app. Complete runtime/source/WAV hashes are bound before dispatch.

Fresh target admission: CPUs2/3,quota200%,one native thread,Tasks64,1MiB stack, hardAS1536MiB, initial availableRAM1408MiB, disk5GiB. Existing sampled guards stop only the owned service below192MiB availableRAM or above1152MiB modelRSS; no hardRSS/MEMCG/no-swap guarantee. This longer protocol has600s service,590s worker alarm,10s stop. Combined host+target output reserve32MiB;4MiB service log and2MiB per JSON file limits. The research lease and exact boot/PID/start identity last through closure. Actual live unit properties are retained. Original app concurrency makes timings conditional.

Two streams use1280sample pushes with every source sample, native EOF and idempotent finish/post-finish rejection. Require nonempty text in each, identical canonical events (availability-clock values excluded), and explicit stream/model closure. Record session completion receipts while running. Any abort, alarm, output or memory-guard stop is failure, never acceptance. Existing short/failure/build evidence is immutable.

PowerShell, from campaign worktree:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/a2_native_full_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V37.json'
```
CMD / Anaconda Prompt, no activation required:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\a2_native_full_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V37.json
```
Use a fresh window_guard_v2 census less than15minutes old. Fixed ID refuses overwrite; gate/worker entry points are internal. Outputs stay private in a2-native-full-v1 on target and a2-native-full-v1-evidence on host: admissions/bindings, live envelope, exact owners, session/event/results, bounded logs and resources. Independent review must check full715127sample passage, event equality/nonempty text, native timestamps, finish/reset/closure, model/source hash, executed envelope, output bound and baseline preservation. Keep transcripts private. A later separate protocol must cover forced endpoints and matched baseline parity before general native ASR acceptance.
