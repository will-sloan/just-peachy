# Bounded waveform D1 runtime and original-model comparison

Purpose: join the separately tested NumPy frontend, ordered cache/FIFO state and high-resolution ONNX graph into one16kHz mono stream. Only delayed264/1/1/0/264/188 and at most715127samples are admitted. No capture, labels/UI, ASR/E0, download or new model export. Existing coefficients/graphs are reused unchanged; the actual checkpoint learnable_sil_emb is extracted in the original-model reference run, not replaced with synthetic fixtures.

Inputs: pinned D1checkpoint, high-resolution V4graph, small compression V2graph, original frontend coefficients and private original44.6954375-second WAV. push requires finitefloat32mono<=32768samples and exact source_start; one owning thread; reset restarts all sample/feature/cache origins. No gaps concatenated or audio skipped. At most2334 transient feature rows, at most512persistent frontend samples; chunks wait for2112new+8right features, retain8left. finish consumes frontend tail and final model chunk, then rejects additional pushes/finish. close releases both ORT sessions. Cases include1281sampletail, fullsource with fixed/irregular/fixedrepeat, reset and malformed/discontinuous/postfinish rejection; sub160sample inputs produce no valid features/modelcalls by explicit frontend contract.

Reference: untouched installed NeMo model.forward with streaming_modeTrue, asyncFalse, samegeometry, FP32/eval/dither0. Observe original forward_streaming_step only to retain chunk/state evidence. Its forward crops preprocessor padding to validfeaturelength before streaming. Therefore715127samples produces4469valid probability rows at10ms frame centers, not4480paddedfeatures and not prior native-Q8's4470rows. Preserve87subhopremainder samples as explicit metadata; no extra probability or phonetic-alignment claim. Original PyTorch full repeat must be exact. Candidate fixed/irregular/repeat outputs and final cache/FIFO values must match original at predeclared maxabs1e-5 and each other exactly. Never relax the output gate if tiny frontend errors amplify. No Q8 equality or accuracy scoring.

Output: fresh private d1-onnx-waveform-v1, original/candidate probability and state arrays, actual learned embedding, source hashes, per-stage costs, buffer/mapping/closure receipts and failures. Candidate trace records valid source-feature intervals, context, highres offset and discarded model padding. Full-source numerical pass is still not live/GUI/endurance/release qualification. Runtime APIs consume caller-provided files and do not select a backend silently.

Admission: WINDOW_V4,52GiBtotal/4GiBcombinedoutput with2.5GiBreservations and targetbytes counted;64MiBnewoutput,600seconds,hard6GiBhostjobcommit,CPU4/14total2/model1thread/coordinator14,GPUoff,12GiBinitial/8GiBrunningRAM,C50/G75GiBfloors. Fresh supervisor/owner+target boot/unit/lease/resource checks; original closed ledger and baseline untouched. File-size stop is sampled, not quota. Fixed run refuses existing root; no direct worker/guard invocation outside supervisor.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_waveform_launch_v1.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V55.json
```
CMD / Anaconda Prompt (no activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_waveform_launch_v1.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V55.json
```
Census must be fresh within15minutes. Review closed results with README_REVIEW_D1_WAVEFORM_V1.md. Native admission/source binding still required before deploying candidate to Pi; runtime preparation alone is not acceptance.
