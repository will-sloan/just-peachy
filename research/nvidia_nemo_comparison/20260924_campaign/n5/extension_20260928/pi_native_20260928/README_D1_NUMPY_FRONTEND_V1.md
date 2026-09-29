# Portable D1 frontend candidate and reference checks

Purpose: convert finite mono16kHz float32 audio to the pinned D1 frontend's128 log-mel features without torch/NeMo/SciPy on the Pi. Uses preserved checkpoint-derived window/filterbank coefficients, continuous0.97 preemphasis, centered512FFT/400window/160hop, constant edge padding, magnitude-sqrt-then-square and log-add2^-24. No dither/normalization. The512FFT window needs256samples (16ms) of right context; it is not zero-lookahead. Persistent history stays<=512samples; maximum input push32768. Empty/EOF/reset are explicit, invalid/post-finish input fails. No graph, speaker cache or model runs in this candidate.

Inputs: private frontend_buffers.npz from reviewed exportV3 and already saved original16k source. Outputs: valid sequential `[frames,128]` features; optional batch padding matches NeMo's extra masked frame/pad-to16. No state/source gaps are removed. Tests compare pinned unmodified NeMo FilterbankFeatures with copied exact coefficients against both fixed and irregular pushes, repeats/reset, empty/one/hop/tail/full, zero and impulse inputs. Raw arrays stay private.

Predeclared frontend gate: maximum absolute log-feature difference1e-4 across FFT implementations, exact valid lengths/shapes/zero padding, finite arrays and unchanged inputs. This is a separate frontend gate, not a relaxation of the existing1e-5 D1 output gate. Full downstream probability parity remains necessary. No audio accuracy, latency improvement, full diarizer or release claim follows.

Host supervised reference preparation, PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_frontend_launch_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V45.json'
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_frontend_launch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V45.json
```
Fixed fresh private run d1-onnx-frontend-v1 refuses existing output. Requires a fresh V3 census and target-inclusive admission for32MiB output under original50GiB payload/reservations and4GiB window. Existing host supervisor runs in a fresh isolated state directory; CPU4/14total2/coordinator14,one native thread,GPUoff,hard6GiB jobcommit,600seconds,host available RAM floors12GiB start/8GiB running,C50/G75GiB. Byte cap is sampled. Installed NeMo source/weights and old export runs stay unchanged. Internal --guard/--root paths must not be invoked separately. Reference preparation is Pi-related host work; native proof needs its own admission/reader.
