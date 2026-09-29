# Stage the new reviewed four-output high-resolution graph only. No model inference, capture or playback.

Inputs: Host d1-onnx-export-v4 graph: 400460634bytes, SHAdd3225f3f14c2e6436f643f2e985865075f8e6a5e48034640825c8d0e9b1445a; independent host REVIEW; fresh V4 census.

Outputs: Fresh target d1-onnx-stage-v2/D1_highres_fp32.onnx and source/admission/live unit/closure receipts. Immutable V1 graph remains intact.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/stage_d1_onnx_v2.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V52.json
```
CMD / Anaconda Prompt (no activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/stage_d1_onnx_v2.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V52.json
```
Fixed fresh IDs refuse existing output. Internal receive/gate/worker flags are registered service entry points, not manual launch commands. Review only after exact owners close. Keep old failures/graphs; no fallback or installed-source edits.

Transfer admission:416MiB including graph, hard128MiB address space/1MiBstack,CPU2/3 quota200%,Tasks64,600s/10sstop,initial850MiBavailable/disk5GiB+reserve, original owners/config/boot/capture and both leases checked. Receiver persists live properties before transient collection, reads at most declared graph bytes and rejects extra/short input. Window4GiB and total52GiB with2.5GiB reservations/hostdrivefloors count all target bytes.
