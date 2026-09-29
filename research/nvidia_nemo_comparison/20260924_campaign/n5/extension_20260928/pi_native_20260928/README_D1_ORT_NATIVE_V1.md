# Native D1 ONNX operator, reference and memory cases

Purpose: execute the existing reviewed FP32 graph on CM5's installed ONNX Runtime1.29 CPU provider. Inputs are the staged graph SHA b4e32f5581339a6542a298fc58724b5b0f659978c8d958c53ec378d14a8c79d2 and retained host feature/cache/reference arrays: delayed2128/cache264/FIFO0, cold32/0/0, tail17/cache8/FIFO3. These are constructed feature cases, not audio or ASR/diarization accuracy. Each runs twice in one session, comparing native outputs to unchanged PyTorch references at max-absolute1e-5 and exact lengths; repeats must be exact and inputs unchanged. Do not relax the gate after observing results.

An isolated1536MiB virtual limit is admitted for this first FP32 load because the400MB serialized graph requires initializer/loading/activation headroom. Initial available RAM>=1408MiB, sampled stop below192MiB available or modelRSS>1152MiB; no hardRSS/MEMCG/no-swap claim. CPU2/3,200% total,one native/intra/inter thread,Tasks64,1MiB startup stack,GPUoff,300s service/290s alarm/10s stop,disk>=5GiB. CPU provider only, sequential execution, BASIC graph optimization, spinning disabled. Save live unit limits before collection. Original app remains active, making timings conditional. No capture/playback or baseline changes.

Reuse staged graph without copying it again.32MiB new-output reservation includes case-input copies, results, native arrays, logs and receipts; combine target bytes with current host-window/payload census.4MiB individual file limit and retained service-log bound;2MiB JSON bound. Graph stage receipt must independently pass first. Research flock and exact dispatch owner held through completion; inspect isolated host export owners as well as original supervisor. No frontend/high-resolution/state-driver/full-file or real-time acceptance follows from these three cases.

Outputs: private target `d1-ort-native-v1` plus host `d1-ort-native-v1-evidence`, including exact admissions/owners/live envelope, providers, load/call times, first/repeat arrays, source checks, memory samples, failure or natural closure. Failed partial results stay preserved. Independent reader is required; launcher exit0 is not acceptance.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_ort_native_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V41.json'
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_ort_native_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V41.json
```
Fresh census under15minutes and immutable new run ID required. `--worker`/`--gate` are internal registered entry points. Preserve failures and use a fresh derivative for any changed settings.
