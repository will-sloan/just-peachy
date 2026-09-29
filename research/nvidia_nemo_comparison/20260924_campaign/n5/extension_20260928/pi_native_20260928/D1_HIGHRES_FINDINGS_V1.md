# Learned high-resolution ONNX outputs: native component qualification

September29,22:02UTC. CHECK_SUMMARY_V35 binds independent host, transfer and actual Pi readers. The alternate FP32 graph now retains original learned high-resolution probabilities as its fourth output, alongside coarse state probabilities, pre-encoded embeddings and lengths. No repeating/interpolation of coarse probabilities is used to fabricate learned output.

The reference executes pinned NeMo forward_for_export and observes its original forward_infer values before downsampling. The new explicit wrapper matches that reference exactly before the previously qualified dense-attention/dynamic-padding export transformations. Every transformed output also matches original PyTorch exactly in the three cases. Installed NeMo/checkpoint and old graph versions remain unchanged.

New graph400,460,634bytes,SHAdd3225f3f14c2e6436f643f2e985865075f8e6a5e48034640825c8d0e9b1445a. Host export and exact resident repeats independently pass1e-5. Its only Pi copy is d1-onnx-stage-v2/D1_highres_fp32.onnx; bytes/hash/live service properties/natural owner closure separately pass. Do not recopy it or rerun unchanged cases.

| Actual Pi ORT1.29 CPU case | First/repeat seconds | Maximum learned-output error |
|---|---:|---:|
|2128featureframes/cache264/FIFO0|5.514/5.717|1.363e-7|
|32features/emptycache/FIFO|0.047/0.040|2.608e-7|
|17features/cache8/FIFO3|0.120/0.126|1.252e-6|

All four outputs pass the unchanged1e-5 gate; embedding maximum6.676e-6, integer lengths exact, inputs unchanged, resident repeats bit-exact. Load3.523seconds; kernel peak508.734MiBRSS. BASIC optimization/sequential/single CPU thread, admitted1536MiB virtual limit, original rc5 concurrently active. Constructed features are not waveform duration, audio RTF, a speedup, held-out accuracy or sustained fit. No silent backend fallback.

All147recorded Pi and32isolated host identities closed at22:02UTC; captureclosed,bothleasesfree,originalboot/app/config/install unchanged. Independent natural process/session closure and actual live unit envelope pass. Host output405,914,635bytes/512MiB; Pi graph stage400,476,804bytes/416MiB; native case evidence5,317,288bytes/32MiB. No microphone/playback, baseline edit, OS/boot/swap change or download occurred.

Fresh WINDOW_V4/window_guard_v4 implements the already-authorized measured total-payload adjustment50to52GiB for future admissions only. The old cap had184,889,170bytes of measured headroom, insufficient for~800MBnewhostgraph+Pi copy. Preserve old50GiBpolicies/ledgers/evidence and2.5GiBreservations;4GiBcombined-output window, C50/G75GiBfreefloors, CPU/RAM/deadline unchanged. Four meaningful arithmetic boundary tests pass after explicitly setting coordinator14; first test-placement caveat and corrected static stack-review predicate are retained privately, and executed envelope verification independently passed. Latest combined3,920,046,920/4,294,967,296bytes; about357.6MiB window space remains. Fresh accounting remains mandatory.

Next integrate the separately qualified NumPy frontend, ordered state/small compression graph and this main graph into one ordered waveform/source-clock/EOF runtime. Read upstream streaming_feat_loader and forward_streaming_step: feature chunks2112frames plus0/8left and0/8right; last batch includes pad-to16 masked feature positions. High-resolution selection begins at(cache+FIFO+leftcoarse)*8. Preserve raw/padded versus valid lengths explicitly:4469valid frontend frames are not the old native4470probability count, and neither implies a completed source mapping. Extract the actual checkpoint learnable_sil_emb in the next admitted original-model reference run; synthetic state-fixture embeddings must not substitute. Predeclare full-source/repeat/reset/EOF/state/mapping gates before dispatch; no full runtime or release is accepted yet.

Execution/readers: README_D1_ONNX_EXPORT_V4, README_REVIEW_D1_ONNX_EXPORT_V4, README_STAGE_D1_ONNX_V2, README_REVIEW_STAGE_D1_ONNX_V2, README_D1_ORT_NATIVE_V2, README_REVIEW_D1_ORT_NATIVE_V2. Each includes purpose, inputs/outputs and PowerShell/CMD/Anaconda commands. Bound source/readmes remain immutable. Keep bounded quietPCM/journaling, GUI readiness and A2optimized/sequential work moving alongside runtime integration.
