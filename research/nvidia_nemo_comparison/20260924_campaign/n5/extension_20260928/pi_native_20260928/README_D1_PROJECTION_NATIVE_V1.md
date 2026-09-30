# Native natural-feature projection diagnosis

Purpose: determine whether the Pi reproduces the already localized host FP32 preencoder discrepancy before selecting a repair. This is a new ARM check, not a rerun of the full waveform or prior constructed features. The unchanged 1e-5 probability/state gate remains; collecting a discrepancy with exit0 is not numerical acceptance.

Inputs: the reviewed 2,105,077-byte preencoder graph extracted from the immutable high-resolution FP32/opset17 graph, plus the four exact retained natural-feature/stack/PyTorch/host-ORT fixtures (tail8, first2120, middle2128, final253 frames). No full graph/model copy, checkpoint extraction, downloads or newly generated references. CPU-only ORT, sequential execution, BASIC optimization, one intra/inter thread and the same enabled CPU arena as the host diagnostic. Each case runs twice in one session. Check exact stack/padding/lengths/input bytes, finite outputs and repeat; record errors against original PyTorch and host ORT separately. No microphone, playback, ASR, full diarizer, GUI or accuracy measurement.

Outputs: fresh private target `d1-projection-native-v1` contains bound inputs, first/repeat NPZ outputs, resource/live-envelope/owner/result receipts. Host `d1-projection-native-v1-evidence` retains launch/admission and later independent review/verified backup. `NATIVE_PROJECTION_OBSERVATIONS_REVIEW_REQUIRED` explicitly means observations awaiting review; no full-runtime or speedup claim.

Admission: WINDOW_V5,52GiB payload including target and retained2.5GiB reservations,5GiB combined output. Reserve64MiB for staging/results plus host backup; target sampled output cap32MiB, staged inputs<20MiB, per output file4MiB/log4MiB. Hard768MiB virtual/1MiB stack,CPU2/3,total200%,Tasks64,one model thread,GPUoff; require850MiB available and5GiB free disk plus reservation. Sampled stop below192MiB available or above640MiB worker RSS, not hard RSS enforcement.300s service/290s worker alarm/10s stop. Preserve OS/swap and original app/config/install; existing research flock, exact boot/owners/units and hardware-lease closure apply. Live systemd properties are saved before collection. No output allowance is reset.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_projection_native_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V88.json
```

CMD / Anaconda Prompt (no environment activation required):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_projection_native_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V88.json
```

Use a fresh unused census under15minutes; fixed target and receipt roots refuse overwrite. `--gate`/`--worker` are internal owned entry points, not independent launch authorization. Independent review must verify exact inputs/outputs and numerical limits, actual service envelope, natural process closure, baseline/leases and backup before reporting findings. Preserve every earlier failure; the fixed32GB device is unchanged. Close before October1 17:47:34UTC.
