# D1 native streaming, reference parity and validation

This folder builds and verifies the actual standalone Nemotron 3 anonymous diarizer for N2. It preserves the official eight channels and streaming speaker-cache state, explicitly selects model/profile, and records raw probability/timing evidence. No ASR/TTS model, microphone, playback, source transcript or source identity is passed into this predictor. It uses saved accepted S4.5 audio only, with unity additional gain.

Prerequisites: the existing N1 pinned source and build receipts, Visual Studio 2022 C++/CMake, content-addressed official Q8, and the existing app Python interpreter with NumPy, SoundFile and psutil. Large output goes under `G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization`; retain at least 75 GiB free on G:. No activation or installation into the application environment is required.

PowerShell, starting in the campaign worktree:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$pythonN2 = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$scriptsN2 = 'research\nvidia_nemo_comparison\20260924_campaign\n2\diarization'
& $pythonN2 "$scriptsN2\build_native.py"
& $pythonN2 "$scriptsN2\fetch_reference.py"
& $pythonN2 "$scriptsN2\run_native_panel.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\my-new-panel' --functional
```

Command Prompt or Anaconda Prompt:

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree"
set "PYTHON_N2=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "SCRIPTS_N2=research\nvidia_nemo_comparison\20260924_campaign\n2\diarization"
"%PYTHON_N2%" "%SCRIPTS_N2%\build_native.py"
"%PYTHON_N2%" "%SCRIPTS_N2%\fetch_reference.py"
"%PYTHON_N2%" "%SCRIPTS_N2%\run_native_panel.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\my-new-panel" --functional
```

`build_native.py` reads the frozen N1 runtime receipt, copies its source to N2, changes `ggml_graph_compute_helper_async(...,4)` to `(...,1)` after checking the expected site, and builds `nemo_speech_asr_c` with all existing no-microphone/no-CUDA/no-TTS options. The Windows text write also normalizes line endings in that copied source file; the thread argument is the only semantic change. It uses one compiler job and below-normal child priority. Output: `NATIVE_BUILD_RECEIPT.json`, private DLLs/source/logs. Optional `--output` selects the private build directory. The existing N1 source/build are untouched.

`fetch_reference.py` reads the frozen official model metadata, downloads only the pinned `.nemo` counterpart, checks its exact official LFS size/SHA256, and inspects its archive/config without deserializing weights. It emits `REFERENCE_ARTIFACT_RECEIPT.json` and the private checkpoint/config. Ordinary official OpenMDW 1.1 model terms are recorded in the N1 license receipts. Native code remains Apache-2.0 with dependency notices retained in the copied source.

`run_native_panel.py` loads the hash-bound Q8 and CPU-one-thread DLL, then reads the audio-only fixed screen manifest. Default input is the first 12 seconds of job 0, S45_01_04 O0. `--job-index 1` chooses its matched O1; `--seconds 0` uses the whole admitted file; `--profiles low_latency very_low_latency ultra_low_latency` selects any declared subset. `--paced` delivers saved audio at source speed and is distinguished from accelerated causal delivery. `--functional` additionally checks empty input, constant audio, repeated finish, rejection of post-finish pushes, reset and chunk-partition invariance. Constant input is a functional fixture only, not an acoustic evaluation scene.

Outputs: private `RECEIPT.json` with all availability events, probability NPZ files and optional constant-input NPZ files; redacted `NATIVE_PANEL_RECEIPT.json` (or `NATIVE_PACED_RECEIPT.json`) with hashes, dimensions, resource summaries and functional outcomes. Use a new `--output` directory for every run. Probability values remain local and are not personal gallery vectors. CPU times are process measurements; RSS is sampled after native pushes and Windows peak working set is also recorded. Results are desktop measurements, not CM5/ARM64 performance or total system memory estimates.

The adapter documentation is `prototype/vendor/edge_speech_pipeline/README_N2_NEMOTRON.md`. The actual shared-controller D1/E0 and D1/E1 comparisons are owned by the N2 integration runner; this standalone panel does not claim UI/controller readiness by itself.

`check_native_boundaries.py` verifies the real first-emission sample for each profile, one-sample-before warmup, actual availability timestamps, malformed input rejection, independent reset and teardown. A separate four-frame numerical fixture checks overlap span behavior; that fixture is explicitly not neural inference. Inputs are the same admitted first screen file, Q8 and build receipt. Output is `NATIVE_BOUNDARY_RECEIPT.json`. Run with the app Python and script paths above, replacing `run_native_panel.py` by `check_native_boundaries.py` and omitting its flags.

## NeMo reference probability parity

The shared isolated environment is owned by the N2 embedding setup: `G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe`. It uses pinned official NVIDIA-NeMo/Speech revision `cf724ac337d1ebc7d0dda1e23fb80916f52927a5`, Python 3.12 and CPU PyTorch. It must contain NumPy, SoundFile and psutil. Do not install these packages into the original app environment. The checkpoint is fetched and hash-verified by `fetch_reference.py` before any model restoration.

PowerShell:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe' 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\diarization\run_reference_parity.py' --native-panel 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\panel-v1' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\my-new-reference'
```

Command Prompt or Anaconda Prompt:

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\diarization\run_reference_parity.py" --native-panel "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\panel-v1" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\my-new-reference"
```

Replace `--native-panel` with the actual previously completed native evidence directory; `--output` must be new. The reference calls official `forward_streaming_step` with persistent speaker cache/FIFO and the same three profiles. For each eligible step it computes features from the arrived waveform prefix only. This slower diagnostic frontend is measured and is not presented as a deployable or source-paced reference. No full-file model call is passed off as streaming. It runs CPU float32 with dither disabled and one numerical thread.

Outputs are private reference probability NPZ files, per-step cache sizes/timestamps/resources and `RECEIPT.json`, plus redacted `REFERENCE_PARITY_RECEIPT.json`. The comparison preserves original slot order and clocks, reports probability differences, raw 0.5 activity/overlap disagreements and segment/boundary differences on common supported frames. It does not force bit equality, fit time shifts, rename model slots, or claim gold DER. Native and NeMo valid final frame counts can differ by one centered-STFT endpoint frame; both original tails remain stored and explicitly counted.

Both panel runners accept `--receipt-name NAME.json` to retain a distinct redacted receipt for another panel. New runs snapshot their runner source (and the native adapter source) into the private output directory. The initial panel's exact earlier runner source snapshots were reconstructed and verified to match the SHA256 already saved in its receipts after the receipt-name option was added; no numerical evidence was altered.

The bounded additional parity panel uses fixed screen job indices 24 and 25, the matched S45_04_09 O0/O1 pair, its first 24 seconds and `--profiles low_latency ultra_low_latency`. The full N2 factorial screen is separate. Source review and known implementation limits are in `NATIVE_SOURCE_REVIEW.md`. Functional process resource receipts include observed CPU/RSS; they do not establish an otherwise idle-machine benchmark or sustained full-session real-time operation.

## Explicit desktop CUDA build and CPU comparison

CPU remains the default. The optional CUDA route uses the already installed CUDA 12.6 toolkit and the same pinned native source, including the one-thread CPU graph patch. `build_native.py --cuda --jobs 2` selects SM86 and the existing toolkit through CMake's `-T cuda=<toolkit directory>` custom-toolkit option; it does not install a compiler, bypass compiler checks, or change the original N1 runtime. The initial Visual Studio auto-detection failure is retained in `CUDA_BUILD_VS_AUTODETECT_FAILED.json`. Compiler jobs are bounded to one or two and run below normal priority. A successful build writes `CUDA_BUILD_RECEIPT.json`, distinct from the CPU receipt.

`stage_cuda_runtime.py` reads that successful CUDA receipt and copies the existing toolkit's `cudart64_12.dll`, `cublas64_12.dll`, and `cublasLt64_12.dll` into its private binary directory. It verifies source/copy hashes, retains the 75 GiB free-space reserve, refuses different existing DLLs, and updates all `runtime_files` bindings and toolkit license-file references. These local runtime DLLs are not committed or added to a handoff archive.

PowerShell (use a new private build and panel directory):

```powershell
& $pythonN2 "$scriptsN2\build_native.py" --cuda --jobs 2 --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\native-cuda-new'
& $pythonN2 "$scriptsN2\stage_cuda_runtime.py"
& $pythonN2 "$scriptsN2\run_native_panel.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\cuda-parity-new' --device cuda --gpu-index 0 --build-receipt "$scriptsN2\CUDA_BUILD_RECEIPT.json" --cpu-reference 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\panel-v1' --receipt-name CUDA_PARITY_RECEIPT.json
```

Command Prompt or Anaconda Prompt (using the variables defined above):

```bat
"%PYTHON_N2%" "%SCRIPTS_N2%\build_native.py" --cuda --jobs 2 --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\native-cuda-new"
"%PYTHON_N2%" "%SCRIPTS_N2%\stage_cuda_runtime.py"
"%PYTHON_N2%" "%SCRIPTS_N2%\run_native_panel.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\cuda-parity-new" --device cuda --gpu-index 0 --build-receipt "%SCRIPTS_N2%\CUDA_BUILD_RECEIPT.json" --cpu-reference "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\panel-v1" --receipt-name CUDA_PARITY_RECEIPT.json
```

The comparison uses the same first 12 seconds, 100 ms delivery blocks, all three profiles, eight original slots and original clocks as the completed CPU panel. It stores raw probabilities, CPU/CUDA probability differences, 0.5 activity/overlap differences, boundary differences, process CPU/RSS and global `nvidia-smi` snapshots. The device snapshots include other desktop allocations and are not process-isolated peak VRAM. Native GPU selection fails if unavailable; there is no automatic CPU retry. CUDA may use CPU support operators. CUDA results are a distinct desktop configuration, never CM5/ARM64 or 2 GB system-memory qualification.

The actual `cuda-parity-v1` launch used a separate below-normal, hidden PowerShell `Start-Process` with stdout/stderr redirected to private files and `WaitForExit(300000)`; timeout would kill only that owned child. It exited 0 without timeout. `CUDA_EXECUTION_RECEIPT.json` binds its exact argument array, launch/exit record and logs. `CUDA_PARITY_RECEIPT.json` additionally records the actual different-runtime-directory rejection after all three CUDA models closed. These guard checks do not load the CPU DLLs into the CUDA process.

## Checkpointed complete fixed screen

`run_fixed_screen.py` produces raw D1 evidence for the same frozen 96 audio-only jobs (48 matched O0/O1 pairs), for one or all three profiles. It validates input/header hashes, unity gain, model SHA, every native runtime DLL, Python/package identity, source snapshots, streaming geometry and the absence of additional predictor fields. Each profile keeps one model resident and resets its stream only between independent scenes. Audio is delivered causally in 1,600-sample blocks plus a final remainder and explicit flush; this accelerated file replay is not labelled source-paced. It loads no ASR/TTS or gold labels and performs no diarization-quality scoring.

Outputs are private `ADMISSION.json`, `PROGRESS.json`, `RESULT_INDEX.json`, OS-owned `WRITER.lock`/owner metadata, bounded worker logs, and per-cell immutable attempt folders. Each attempt stores `probabilities.npz` (frames by eight), every push's availability in `AVAILABILITY.jsonl`, resource samples, heartbeat, result and hash bindings. A `CHECKPOINT.json` selects the latest attempt without destroying earlier attempts. The resident process has one input in flight, CPU graph threads fixed at one and below-normal priority. Timeout, memory/IO capacity and admission failures are distinct from bad scores (`quality_status: NOT_SCORED`). A timed-out owned worker receives a bounded stop/terminate sequence; the coordinator never kills unrelated processes.

Start with `--prepare-only`, which validates and snapshots all inputs but never loads the native library/model. After the campaign coordinator assigns a numerical slot, remove that flag. `--limit 1` dispatches one entire pending scene, not a truncated sample. Repeating the exact command/output resumes after verifying completed evidence; source, DLL, model, profile, device, input or timeout changes require a new output directory. Failed attempts remain excluded unless `--retry-failed` is explicitly supplied. The default per-scene timeout is 1,800 seconds, model-load timeout 120 seconds, and free-space reserve 75 GiB. Optional `--cpu N` pins the single worker to an allowed CPU. An existing live coordinator/worker prevents a second writer.

PowerShell, CPU default preparation for the two additional profiles:

```powershell
& $pythonN2 "$scriptsN2\run_fixed_screen.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cpu-new' --profiles very_low_latency ultra_low_latency --prepare-only
# After coordinator dispatch, a one-scene smoke:
& $pythonN2 "$scriptsN2\run_fixed_screen.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cpu-new' --profiles very_low_latency ultra_low_latency --limit 1
```

Command Prompt or Anaconda Prompt:

```bat
"%PYTHON_N2%" "%SCRIPTS_N2%\run_fixed_screen.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cpu-new" --profiles very_low_latency ultra_low_latency --prepare-only
rem After coordinator dispatch, a one-scene smoke:
"%PYTHON_N2%" "%SCRIPTS_N2%\run_fixed_screen.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cpu-new" --profiles very_low_latency ultra_low_latency --limit 1
```

For a separately admitted CUDA output, append `--device cuda --gpu-index 0 --build-receipt <path to CUDA_BUILD_RECEIPT.json>` to preparation and dispatch commands. Omit `--profiles` to include all three profiles (288 cells). Omit `--limit` to dispatch all remaining cells only when the campaign coordinator grants ownership; GPU execution requires exclusive GPU ownership and separate device-resource monitoring. The runner records CPU/RSS and CUDA identity but does not claim process-isolated peak GPU memory.

The actual first full-scene smoke used all default profiles, `--device cuda --gpu-index 0 --cpu 14 --limit 1`, the CUDA build receipt, and output `local/n2/diarization/fixed-cuda-all-v1`. It completed `low_latency/N1_BASELINE_S45_01_04_O0`, delivering the entire 44.6954375-second file. `CUDA_FIXED_RUNNER_SMOKE_RECEIPT.json` binds the result. The campaign coordinator may resume that same output with the same bindings and without `--limit 1`; a new incompatible binding requires a new output directory. Do not start a second owner while the supervisor is running it.

That full output completed 288/288 native cells after an IO-only recovery at 195 cells. Windows briefly denied replacing the progress file; the original numerical runner and admission remain unchanged. `resume_native.py` adds bounded parent JSON replacement retries, preserves the incident/amendment, verifies completed checkpoints and runs only pending cells. Purpose, arguments, outputs and both shell commands are in [README_IO.md](../README_IO.md). `FULL_NATIVE_SCREEN_RECEIPT.json` binds completion and proves all 195 existing result bindings survived unchanged; quality scores remain separate.

`check_screen_protocol.py` validates preparation/resume against all 96 real admitted headers/hashes, rejects changed contracts, rejects a competing writer process, reacquires a released lock, detects changed synthetic evidence, and bounds a waiting synthetic child process. It performs no neural inference or GPU work. Input is a fresh `--output` below private `local/n2`; outputs are private command logs and `RECEIPT.json`, plus versioned `SCREEN_PROTOCOL_RECEIPT.json`. From PowerShell: `& $pythonN2 "$scriptsN2\check_screen_protocol.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\protocol-new'`. From Command Prompt or Anaconda Prompt: `"%PYTHON_N2%" "%SCRIPTS_N2%\check_screen_protocol.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\protocol-new"`. A screen run exits 2 if any cells failed, while its index preserves the complete denominator; successful preparation or failure-free partial/completed dispatch exits 0, with partial versus completed status explicitly recorded in `PROGRESS.json`.
