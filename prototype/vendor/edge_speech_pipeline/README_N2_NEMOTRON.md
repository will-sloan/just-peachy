# Native Nemotron 3 streaming diarization

`nemotron_diarization.py` provides D1 anonymous activity from the exact official Nemotron 3 Q8 artifact through NVIDIA's standalone C ABI. It loads no ASR/TTS model. It accepts finite mono float32 audio at 16 kHz, at runtime gain 1.0, and returns incremental eight-channel activity probabilities, session track IDs, frame indices and actual monotonic availability timestamps. Activity is not a personal identity or an enrollment embedding.

The `low_latency`, `very_low_latency`, and `ultra_low_latency` profiles explicitly set chunk/right-context frames to 9/4, 6/2, and 3/1, respectively, with zero left context, 264 FIFO, 264 speaker-cache and 222 update frames. Geometry units are 80 ms. Native output is approximately 10 ms. The centered 512-point feature window adds a 6 ms first-chunk scheduling requirement beyond the nominal 1.04/0.64/0.32 s buffer. Compute and caller delivery batching add further delay. Do not report the nominal buffer as measured latency.

Create `NemotronDiarizer(model_path, library_path, profile='low_latency', session_id=...)`; call `push(samples)` for each arrived block, `finish()` once at session end, and `close()` at teardown. `reset(session_id=...)` creates an independent stream on resident weights. Never reset at ordinary speaker or ASR endpoint boundaries. Slots are fixed within a session; there is no evaluator-driven channel recycling. More than eight physical speakers remain unresolved; eight output slots cannot independently detect overflow.

The optional `gpu=-1` constructor argument defaults to CPU. A nonnegative explicit index (for example `gpu=0`) requires a separately built, hash-bound CUDA runtime. The pinned backend throws if the requested GPU is missing or initialization fails; this adapter never retries on CPU. CUDA graph scheduling can still use CPU-supported operators, with the reviewed one-thread CPU limit. Report the CUDA configuration separately from CPU portability measurements. `manifest()` records `gpu` and `gpu_device_index`; callers must also bind every DLL from the chosen build receipt.

The adapter permits only one native runtime directory per process. CPU and CUDA DLL sets share dependency basenames; switching directories after a load attempt is rejected even after `close()`. Multiple models and streams from the same directory remain valid. Run CPU/CUDA comparisons in separate processes and compare their saved probability arrays. Failed binding/model creation releases the adapter's DLL-directory handle while retaining the process selection guard.

`DiarizationUpdate.probabilities` has shape `[new_frames,8]`; `frame_start` and `seconds_per_frame` place it on the original audio clock. `available_at_monotonic` is captured after the native operation and copying probabilities. `activity_spans(0.5)` creates contiguous diagnostic threshold spans and retains overlap. It does not impose uniform word timing, pad speech boundaries, or convert activity to naming confidence. A final centered-STFT frame may extend beyond the real sample support; consumers must preserve this fact and intersect waveform extraction with received samples.

Use the N2 CPU-one-thread runtime, whose manifest records the exact reviewed native thread-count patch and DLL hashes. The original official runtime hardcodes four graph threads. Build and validation entry points, inputs, outputs and all launch commands are in [the campaign README](../../../research/nvidia_nemo_comparison/20260924_campaign/n2/diarization/README.md). The original N1 release and model artifacts remain unchanged.

From PowerShell, run the actual saved-audio validation:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\diarization\run_native_panel.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\my-new-panel' --functional
```

From Command Prompt or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\diarization\run_native_panel.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\my-new-panel" --functional
```

The output directory must be new. It contains no copied audio: probability NPZ files, timing/resource events and hash-bound JSON receipts are written there. The runner uses only admitted saved files, one CPU thread and below-normal priority. No device enumeration or microphone/playback calls occur.
