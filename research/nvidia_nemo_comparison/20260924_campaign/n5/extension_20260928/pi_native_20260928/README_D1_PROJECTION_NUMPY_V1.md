# Native NumPy projection accumulation experiment

Purpose: test exactly one alternate FP32 CPU matrix kernel for the measured D1 preencoder mismatch. Earlier receipts establish identical weights/stacking and identical host/Pi ORT results but a failure against original PyTorch at1e-5. This candidate replaces only that matrix multiplication with existing NumPy's FP32 `stack.reshape(-1,1024) @ original_weight.T`. It is not a parameter sweep, new reference, mixed-precision runtime or change to the deployed application. The complete D1 runtime remains unqualified until all original probability AND state gates pass.

Inputs: original checkpoint-derived projection_weight.npy (512x1024) hash8f73ad686c7df5485d35a2acb137895e98f0ba89d69bfd3e4f0e299fcc324c8a, bound host review and four already-staged natural stack/PyTorch/ORT/float64 diagnostic fixtures at d1-projection-native-v1. Only the2MiB weight is staged; no full graph, checkpoint extraction, feature copies, downloads or model reruns. The four fixed shapes cover tail, first, middle and final chunks, with exact resident repeat and immutable input checks. NumPy build configuration is recorded. Both passes compare against the unchanged1e-5 original PyTorch gate, retained ORT observations and float64 diagnostic arrays. Float64 is used only to measure differences, never as a replacement acceptance standard. Collection exit0 is not numerical acceptance.

Outputs: private d1-projection-numpy-v1 holds eight small NPZ outputs, build configuration, admissions, source/weight hashes, exact owners, live unit envelope, result and cost receipts. The separate reader validates arrays without NumPy using the NPY format, checks lifetime/limits and backs up every file with hashes. CPU timings describe this projection only; no full-model speedup, waveform parity, GUI, live capture or accuracy follows. No microphone/playback occurs and original app/config remain unchanged.

Bounds: WINDOW_V5,52GiB total including target/reservations and5GiB combined output. New32MiB combined reservation splits16MiB target and16MiB host backup. Hard768MiB AS/1MiB stacks,CPU2/3 shared200%,Tasks64,one NumPy/model thread,GPUoff,300s service/290s alarm/10s Stop,4MiB per-file/log limit. Initial850MiB available RAM,5GiB target free plus reservation; sampled stop192MiB available/640MiB RSS, not hard RSS enforcement. Actual fixed32GB device remains unchanged. Research flock, hardware lease availability, exact boot/PIDs/baseline hashes and live systemd properties must pass. No usage reset or old evidence edits.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/d1_projection_numpy_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V103.json'
& $py -B "$p/review_d1_projection_numpy_v1.py"
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"%PY%" -B "%P%\d1_projection_numpy_v1.py" --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V103.json
"%PY%" -B "%P%\review_d1_projection_numpy_v1.py"
```

Use the existing interpreter, no installation. Census under15minutes, fresh target-inclusive budget and all owners closed are mandatory. Run name is single-use and refuses overwrite; --gate/--worker are internal dispatcher entry points. Preserve every result including failed parity. Any repair requires a justified fresh derivative, not a gate relaxation or unchanged repeat. Checkpoint October1 17:47:34UTC unchanged.
