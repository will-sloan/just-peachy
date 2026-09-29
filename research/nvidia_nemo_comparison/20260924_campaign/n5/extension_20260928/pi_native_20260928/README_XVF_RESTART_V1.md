# Single XVF firmware recovery v1

Purpose: one documented XVF-only restart after the physically authorized quiet-route attempt `live-ready-user-20260929T161831Z` failed AEC_MIC_ARRAY_TYPE despite receiving priming callbacks. VERSION3.2.1 and INT/lr48/linear/I2C build reads worked. No route setter ran, zero samples were accepted, capture closed and hardware lease released. This mirrors the preserved September20 recovery symptom. The evaluation8hour limit is a possible explanation, not a measured cause or known XVF uptime.

Sources: [XMOS hardware guide](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/02_setting_up_the_hardware.html) documents the evaluation limit and restart; [testing guide](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/programming_guide/04_testing_the_software.html) documents TEST_CORE_BURN0 as firmware reboot. This never enables core-burn1, flashes firmware, changes drivers/OS, or introduces periodic/licence-bypass resets.

Inputs: exact bound source/config/tool/install, fresh host census and target admission, unchanged original app identities, closed capture and all research owners closed. The shared research dispatch lease and original hardware lease are both held. Firmware VERSION/build are read before and after. A persistent RESTART_INTENT is written before one `TEST_CORE_BURN 0` command; an uncertain reply is preserved and never retried. The fixed run directory also prevents a second dispatch. Wait2seconds then read firmware identity. A new user-ready quiet check is required to establish recovery.

Output: private `xvf-restart-v1[-evidence]` admission/intent/command replies/results/exact process identities. No capture, playback, model inference or audio files. Restart resets volatile DSP parameters/adaptive state; unreadable pre-reset DSP state cannot be claimed restored. The original rc5 app/install/autostart/personal files and Pi boot remain unchanged.

PowerShell, from the campaign worktree:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_xvf_restart_v1.py --reset-once --census <fresh-census.json>
```

CMD or Anaconda Prompt (existing interpreter, no activation/install):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_xvf_restart_v1.py --reset-once --census <fresh-census.json>
```

The same CPU2/3,200%,one-thread,Tasks64,hard768MiB address-space,1MiB stack,>=850MiB available RAM,>=5GiB disk,180s service+90s stop and16MiB output reservation apply. No larger cap or downloads. Independently bind command receipt, unchanged VERSION/build, boot/app/config/install, exact owners and closed capture. Firmware readback alone does not prove processing recovery; preserve the original failure and review a fresh quiet check separately. Do not automatically repeat this recovery or launch capture on a scheduled wake.
