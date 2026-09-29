# Launch the bounded anonymous Pi preview

This is the current user launch path. It reuses the V1 restricted controls and V2 native app unchanged, adding an atomic dispatch lease. It is an experimental saved-file preview, not a named-speaker mode, a full release or a real-life accuracy result. No visible preview is automatically opened by the hourly campaign.

## Purpose, inputs and outputs

`launch_b05_preview_v3.py` runs on the Windows host. It obtains a fresh host census, checks code qualification, available resources and exact Pi process identities, and creates a unique admitted run. `b05_preview_gate_v1.py` acquires a nonblocking target file lock and rechecks owners, units, boot, original app/install, dependencies and available RAM/disk. It writes an exact PID/start/boot dispatch-owner receipt, visible to existing research-worker scanners, and holds the lock until the bounded systemd service exits. A simultaneous preview dispatch is refused. The lock does not modify any closed ledger or original app configuration.

The native service runs the unchanged `b05_preview_app_v2.py` and `b05_preview_v1.py` controller/UI. Inputs are the reviewed shared-app-native-gui-v1 source, existing model assets and only the checked44.6954375second16kHz mono PCM16 sample. Outputs are private per-run admission/owner/dispatch/result/memory/session files. Raw audio/text/probabilities and personal data stay out of Git. A user preview needs its own result and exact closure review; prior qualification does not certify a later outcome.

Limits remain CPUs2/3,totalCPU200%,one native model thread,Tasks64,hard768MiBvirtual address space and1MiBstartup stacks. At least850MiBavailableRAM and5GiBdisk, the existing host C/G floors and combined1GiBnew-output allowance are required. No MEMCG, swap, OS or boot setting is changed. No downloads, microphone, playback or enrollment. The original rc5 app keeps running and remains the rollback; timings are conditional on that concurrent workload.

## Open the preview when you are ready

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b05_preview_v3.py --mode user
```

CMD or Anaconda Prompt, using the existing interpreter without installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b05_preview_v3.py --mode user
```

The census can take several minutes. A missing B05_PREVIEW_V3_QUALIFICATION.json, changed source/boot/install, busy research worker, insufficient headroom or expired October1 checkpoint causes refusal; limits are never raised automatically. Do not invoke the target Python app/gate directly outside the admitted host workflow. V1/V2 launchers remain immutable research ancestry and are not enabled for user launch.

On the Pi, choose **File → Choose saved sample → Start file**. The window starts idle; file selection alone does not start inference. **Stop** drains the session; **Start file** restarts at source zero. Anonymous labels may arrive about25seconds later than the source starts; captions run independently. There are no personal names or other mode/backend substitutions. Settings offers **Close preview**. The145second application window permits at most two starts, each requiring75seconds remaining; systemd has a180second hard limit. The window closes automatically and the original app stays in place. Saved-file functional/resource checks do not establish physical layout/touch, sustained real time or speech quality.

## Automatic dispatch-envelope check

Use the same command with `--mode guard-check --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V18.json`. The single-use run is b05-preview-guard-v1. It holds the lease, checks that a second contender exits73 without entering, then executes a small actual systemd job verifying affinity, CPU quota,768MiBaddress cap and1MiBstack. It creates DISPATCH_OWNER/PROBE_OWNER and PROBE_RESULT/DISPATCH_RESULT receipts. No GUI, model, audio or capture runs. Census freshness must be under15minutes; preserve any failed admission and never overwrite evidence.

Combine independent guard review with the V1 full-model actual-button review, V2 idle-loop/timer review and source inheritance before enabling user mode. Read README_B05_PREVIEW_REVIEW_V1.md, README_B05_PREVIEW_IDLE_REVIEW_V1.md and README_B05_PREVIEW_GUARD_REVIEW_V1.md for PowerShell/CMD/Anaconda review commands and scopes. Each path has fresh immutable receipts; none establishes N4/N5 acceptance.
