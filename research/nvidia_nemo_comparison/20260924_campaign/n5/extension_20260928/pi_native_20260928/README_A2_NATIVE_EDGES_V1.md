# Native A2 missing edge cases

Purpose: exercise the remaining empty, one-sample,1281-sample tail and full-source forced-endpoint cases from the original native streaming plan through the qualified Python C-ABI adapter. Reuse the separately reviewed ordinary full-file/resident-repeat result instead of rerunning it. This is not execution of the original standalone C++ six-case reader, malformed-WAV parser qualification, independent runtime parity, WER/accuracy or N5 acceptance.

Inputs: unchanged generic CPU and A2 metadata16/8192/95%guard library SHA6415fb2a77aa5483bbb91e5ecaf5d58c6c3f9edbfe92575f1ab2389d6064bc1b, pinned A2 Q8 weights and original715127sample/44.6954375s16kHz PCM file. Each case starts a fresh stream on one resident recognizer. Force once at sample197440 (12.34s), splitting a1280sample push when necessary; all source samples remain in their original order. Read every result, native EOF, an empty second drain and idempotent finish; reject feed after finish and explicitly destroy streams/recognizer. Record exact force receipt/phase/source position. Empty/short cases need not contain text; full forced case must have nonempty passage. Native word times are model outputs, not reference alignment.

Envelope: isolated hardAS1536MiB, CPU2/3/quota200%, one native thread,Tasks64,1MiB stack; initial availableRAM1408MiB/disk5GiB. Sampled guards below192MiB available or above1152MiBRSS stop the owned service. No MEMCG/hardRSS/no-swap claim. Service300s,worker290s alarm,10s stop. Fresh output reserve32MiB under combined3GiB and original payload/drive floors;4MiB retained service log and2MiB per result file bounds. Research lease and exact boot/PID/start owner held through completion; actual live unit properties saved. Original app/config/OS unchanged; no capture/playback/downloads.

PowerShell from G:\Just_Peachy_N1\20260924_campaign\worktree:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/a2_native_edges_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V38.json'
```
CMD / Anaconda Prompt (no activation required):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\a2_native_edges_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V38.json
```
Use a window_guard_v2 census less than15minutes old. Fixed run ID refuses overwrite. Gate/worker are internal entry points. Private outputs: target a2-native-edges-v1 admissions/bindings/live-envelope/owners/force receipt/per-case events/results/logs and host a2-native-edges-v1-evidence. Independently verify all four cases, sample coverage/phase/EOF/closure, actual envelope and hashes. Keep raw transcripts private; failed attempts remain preserved.
