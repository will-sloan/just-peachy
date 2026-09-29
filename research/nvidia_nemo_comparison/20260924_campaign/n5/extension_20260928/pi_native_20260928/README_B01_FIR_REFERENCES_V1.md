# Filtered B01 D1/E0 references V1

Purpose: independently recompute both application sessions from the exact component-qualified filtered float32 source. This supplements the integration lifecycle review; no old unfiltered arrays are reused as model references.

Inputs: b01-fir-integration-v1 admission/result/events and scoped review, live-decimator-numpy-v1 filtered full array with its reference bindings, unchanged D1 delayed runtime and retained ReDimNet assets. Native standalone D1 replays each early/full session twice in100ms chunks, verifies contiguous frames, reset/EOF/repeated-finish/post-finish rejection and1e-5 application/repeat parity. Direct one-thread ONNX Runtime recomputes every exact0.5–2s application embedding window twice at1e-5. Input bytes must remain unchanged. No enrollment, names, capture/playback or accuracy metrics.

b01_fir_references_v1.py is the native driver; dispatch_b01_fir_references_v1.py constructs the bound private plan and admission; b01_fir_references_gate_v1.py shares the target preview lease. review_b01_fir_references_v1.py separately rechecks plans against original events, hashes, output arrays, tolerances and exact natural owner closure. Raw probability/embedding arrays remain private. Component/application numeric agreement is not acoustic quality or live capture qualification.

Resources: CPUs2/3,total200%,one model thread,768MiB virtual cap,1MiB startupstack,Tasks64,180s service,32MiB new-output reservation,>=850MiB RAM and5GiB disk. D1 closes before E0 loads; existing app/OS remain unchanged. Single-use run ID; census under15minutes; no dispatch during a healthy preview/job.

PowerShell from the campaign worktree:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
$c='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V24.json'
& $py -B "$p/dispatch_b01_fir_references_v1.py" --run-id b01-fir-references-v1 --census $c
& $py -B "$p/review_b01_fir_references_v1.py"
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928"
set "C=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V24.json"
"%PY%" -B "%P%/dispatch_b01_fir_references_v1.py" --run-id b01-fir-references-v1 --census "%C%"
"%PY%" -B "%P%/review_b01_fir_references_v1.py"
```

Outputs: target b01-fir-references-v1 and private host b01-fir-references-v1-evidence retain bound PLAN/runtime/admission/owners/RESULT, repeated D1 and E0 arrays, and independent REVIEW. Acceptance remains limited to this constructed saved-input pair; actual hardware routing, time mapping and sustained/live behavior remain open.
