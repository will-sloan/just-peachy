# Fault-only callback diagnostics: unintegrated candidate

Purpose: preserve the actual callback-status flags next time a live source fails, without changing its stop policy. Inspection of the preserved live_audio.py shows `_dropped_frames += frames` on any nonzero status. The reported480frames counts the rejected callback block; it does not measure all upstream loss or prove a10ms gap. Original evidence remains unchanged and actual flags from the prior trial cannot be recovered.

`callback_fault_details_v1.py` creates an optional subclass of the existing source. Normal callbacks delegate unchanged. Only after the parent raises CallbackAbort it records a bounded scalar tuple containing rejected block size, raw status bits, available flag properties and callback ADC/current clocks, then re-raises the same abort. Off-callback status() renders the tuple. Metadata extraction failure also preserves the abort. No disk/GUI/model/audio-copy work occurs in the fault handler. It explicitly leaves upstream_lost_frames unknown. This changes neither buffer size nor latency and is not an input-gap repair. It is not wired into an application or user launcher.

`check_callback_fault_v1.py` invokes the real qualified app callback with preallocated synthetic arrays and fake PortAudio status/exception objects. Eight native model-free cases compare normal samples/counters, input overflow/underflow/other flags, raw-ring exhaustion, oversized callback, priming and unrelated exceptions. No sounddevice import, source.start, stream construction, control command, microphone, audio file, model or playback. It cannot qualify callback timing, real flag incidence or sustained performance.

Inputs: admitted helper/check/gate/launcher/README and unchanged shared-app-b01-fir-v1 source; fresh host census. Outputs: private callback-fault-v1[-evidence] admission/owners, aggregate case receipts and independent REVIEW. Existing ownership/storage/source/lease checks apply: CPUs2/3,total200%,one native thread,Tasks64,hard768MiBvirtual,1MiBstacks,>=850MiB RAM/5GiBdisk,180sservice/10sstop. Only2MiB reserved within the remaining campaign allowance. No downloads or original-app/settings changes.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_callback_fault_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V34.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_callback_fault_v1.py
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`; same commands without `&`, double-quoted interpreter path. Reuse installed Python. Census under15minutes old. Fixed run/exclusive receipts; preserve any failure and use a new version for repairs. Never automatically capture to exercise these diagnostics.
