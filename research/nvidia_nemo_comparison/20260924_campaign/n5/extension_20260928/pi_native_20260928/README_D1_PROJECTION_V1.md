# Natural-feature preencoder projection diagnosis

Purpose: locate the existing alternate D1 state mismatch before changing a runtime. Prior exact-feature isolation passed full probabilities at1e-5 but failed cached embeddings. The pinned preencoder stacks8frames and applies one bias-free1024-to-512 linear projection. This diagnostic separates stack/padding/length mapping from matrix arithmetic using retained natural feature chunks. It does not relax the1e-5 probability or state gates.

Inputs: immutable FP32 high-resolution graphV4, pinned original NeMo FeatureStacking source/checkpoint, retained full/tail frontend fixtures and original waveform cache references, and prior failed isolation receipts. Read the checkpoint tensor archive in memory only; never extract it to disk or reuse the prior partial extraction. Verify original checkpoint projection weights equal the graph initializer exactly after transpose. Instantiate the unchanged FeatureStacking class with the exact weights; no installed source edits.

Extract only the graph's preencoder ancestors into a new private graph smaller than4MiB, exposing the stacked features alongside embeddings/lengths. The full400MB graph is not re-exported or copied to the Pi. Four fixed cases are tail8features, full first2120, middle2128 and final253. Require exact stacked inputs, lengths, unchanged inputs and resident repeat for each ORT path. Compare PyTorch original FeatureStacking, identical direct PyTorch linear, ORT BASIC and ORT optimizations disabled. A float64 matrix accumulation is diagnostic only, not an applied replacement or acceptance standard. Record all1e-5 violations, output magnitudes and first-cache differences without converting observations into a pass. The optimization toggle tests whether graph optimization caused the known mismatch; it is not a parameter sweep.

Outputs: private d1-onnx-projection-v1/preencoder.onnx, projection_weight.npy, four NPZ intermediate arrays, GRAPH/RESULT and source/owner/envelope/lifetime receipts. The arrays/weights remain private. A status ending OBSERVATIONS_REVIEW_REQUIRED means collection completed, not numerical qualification. No audio playback/capture, accuracy scores, full-waveform rerun, native Pi runtime, GUI, speedup or release claim.

Bounds: fresh WINDOW_V5 measured target-inclusive admission;32MiB output,600s guard,6GiB hard host Job commit,CPU4/14,one model thread,GPUoff,coordinator14,12GiB initial/8GiB sampled available RAM,C>=50GiB/G>=75GiB. Existing isolated supervisor/host export lock and exact model identities apply. Original shared ledgers and sources stay immutable. Root-process RSS samples are not aggregate model peak. No downloads; preserve all prior failures and extracted files. Stop safely before October1 17:47:34UTC checkpoint.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_projection_launch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V85.json
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_projection_launch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V85.json
```
Use a fresh unused census under15minutes old. Fixed root refuses overwrite. Worker --root and launcher --guard are internal supervision entry points, not permission to bypass admission. Independently review arrays, exact weights/input lineage, actual envelope, natural owner closure and output size before attributing a cause.
