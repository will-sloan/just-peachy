# Ordered D1 state candidate

Purpose: implement batch-one ordered speaker-cache/FIFO updates for a future portable D1 driver. Algorithm follows pinned NVIDIA NeMo SortformerModules (Apache-2.0, source SHAead9804248b45153a1abfbe54ba67fab3c1d418da904f025ade5500168e7ee7c). Original installed source stays untouched. Uses264 cache frames,8speakers,512-dimensional embeddings, one learned-silence slot per speaker, pinned score/boost thresholds and either FIFO0/refresh188 or FIFO80/refresh40. This is state arithmetic, not neural inference or named-speaker accuracy.

Inputs: new pre-encoded float32 embeddings, combined coarse cache/FIFO/chunk probabilities, exact coarse source offset, optional one-frame left/right context and a bound512D silence embedding. Outputs: current chunk probabilities and updated bounded cache/FIFO arrays. Fresh predictions replace existing FIFO predictions; cache predictions refresh until first compression, then retained selected history is preserved. No speaker permutation/training, audio skipping or source gaps. Reset starts a new origin; finish closes state only and does not manufacture the waveform/model EOF flush.

**Explicit limitation:** PyTorch does not promise a stable finite top-k tie order. This candidate rejects a finite score tie crossing a selection boundary instead of inventing equivalent cache history. The rejection leaves state unchanged. Disabled minus-infinity slots and the mandatory infinity silence slots are supported. A working complete runtime must resolve/qualify finite ties before exposing this backend. No candidate pass should hide this restriction.

Host protocol compares each state field and output against original NeMo streaming_update, including cache compression, FIFO eviction, context stripping, silence/overlap and reset/repeats. Predeclared1e-5 maximum absolute differences for FP32 output/cache values; exact shapes/lengths/selection correspondence, unchanged inputs and failure atomicity. A constructed tied-score negative case must reject visibly, not count as equivalence. Synthetic silence embeddings/cues in these arithmetic checks do not qualify actual learned model weights or whole-stream predictions.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_state_launch_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json'
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_state_launch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json
```
The private write-once d1-onnx-state-v1 uses existing host supervision, fresh V3 target-inclusive32MiB output admission, original50GiB reservations, CPU4/14total2/coordinator14,one native thread,GPUoff,6GiB jobcommit and600s bound. No capture/playback/download/model inference. Actual Pi state checks and independent review are separate. Never rerun an unchanged passed protocol or modify bound sources. The complete ONNX backend remains unqualified until frontend/state/high-resolution model/EOF integration passes.
