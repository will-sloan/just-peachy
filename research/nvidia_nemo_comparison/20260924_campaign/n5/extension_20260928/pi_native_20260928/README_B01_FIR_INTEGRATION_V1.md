# B01 FIR integration V1: constructed saved input only

Purpose: test the already component-qualified NumPy 97-tap FIR inside a fresh retained-E0 B01 application derivative under the existing native memory cap. No device, capture, playback, enrollment or accuracy scoring. Existing previews and original install remain unchanged.

Application changes are limited to app/live_audio.py StreamingDecimator and a new app/_fir97_v1.py containing the exact qualified coefficients and NumPy implementation. All other parent application files are hash-identical. The test harness substitutes a diagnostic saved FileSource: it expands each 320-sample PCM16 block to 960 samples by repetition, converts with the actual derivative StreamingDecimator, then feeds the resulting float32 samples into the unchanged journal/models at original1x pacing. This is not a hardware callback or verified live route. The original1ms FIR delay and no appended-tail policy are explicit; source intervals retain the current count convention, not acoustic-arrival calibration.

Inputs: original44.6954375s saved16k file, qualified FIR reference coefficients/outputs, retained model assets, fresh host census and target admission. Output is different filtered audio; old unfiltered D1/E0 arrays are not valid references. New filtered-input D1/E0 reference qualification remains required at the original1e-5 gate. The integration reader intentionally reports REFERENCES_PENDING, never a numerical parity pass or stage acceptance. It checks actual converted-stream hashes against independent component output, counts, source origins, reset, inference errors, captions, queues, Stop/full restart, real withdrawn Tk and natural owner closure.

Files: fir97_bound_v1.py provides the bound filter; b01_fir_integration_v1.py runs the test; dispatch_b01_fir_v1.py creates a fresh hardlinked application derivative and binds hashes; b01_fir_gate_v1.py holds the shared nonblocking preview lease; review_b01_fir_v1.py reviews passage/lifecycle and retains the outstanding model-reference gate.

Resources: CPUs2/3,200%total,one native thread/model,768MiB hard virtual address space,1MiB stacks,Tasks64,180s service and140s harness bound,48MiB new-output reservation. At least850MiB available RAM and5GiB disk. Fresh census under15minutes. No OS/boot/swap changes. Output admissions, private source/archives/events/arrays, result and review remain in the named private run/evidence directories. Model weights/audio/vectors are never committed.

## PowerShell

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
$c='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V24.json'
& $py -B "$p/dispatch_b01_fir_v1.py" --run-id b01-fir-integration-v1 --census $c
& $py -B "$p/review_b01_fir_v1.py"
```

## CMD / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928"
set "C=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V24.json"
"%PY%" -B "%P%/dispatch_b01_fir_v1.py" --run-id b01-fir-integration-v1 --census "%C%"
"%PY%" -B "%P%/review_b01_fir_v1.py"
```

IDs are single-use; never overwrite existing output. Do not invoke this diagnostic as a user preview. After collection independently recompute new D1/E0 references from the exact filtered float32 input, then test actual live endpoint/rate/channel/time mapping only when the user is ready. No release or microphone-readiness inference from a prepared source or terminal success.
