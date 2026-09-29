# Prepared explicit maintenance restart v2 â€” NOT EXECUTED

At preparation this code was not executed; consult STATUS.md for later reviewed outcomes.

V1 attempted to use the live adapter for TEST_CORE_BURN0. That adapter intentionally denies commands outside its live allowlist. No reset was sent; the independent reader rejected the misleading terminal status. All V1 evidence is preserved. V2 leaves the live adapter unchanged and separates one maintenance-only command behind explicit user authorization. Do not run it on a heartbeat or infer approval from the earlier quiet-microphone permission.

Purpose/input: after approval, use existing hash-bound xvf_host with literal arguments `-u i2c TEST_CORE_BURN 0`, under the original hardware lease and shared research dispatch lock. No variable command or burn1 is supported. Fresh source/config/tool/install hashes, exact boot/PID/start identities, all research jobs closed, original app identities and closed ALSA capture are required. Firmware VERSION/build must match3.2.1 INT/lr48/linear/I2C before the attempt. Persist intent before the subprocess, maximum2seconds; record success/nonzero/timeout, never retry an uncertain send. Wait2seconds and read only VERSION/build. Do not claim DSP recovery from these reads; review then perform a separately user-ready quiet check.

Effect: reboot only the XVF firmware, clearing volatile DSP settings/adaptive state. The Pi, app/install/autostart and personal files stay unchanged. Unreadable old DSP settings cannot be restored. No firmware flashing, driver/OS changes, audio capture/playback or models. This is a documented manual recovery, never a periodic evaluation-limit workaround. Sources: [XMOS restart](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/programming_guide/04_testing_the_software.html) and [evaluation limit](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/02_setting_up_the_hardware.html).

Private output: xvf-restart-v2 admission, RESTART_INTENT, MAINTENANCE_COMMAND with exact argv/exit/stdout/stderr or timeout, firmware readbacks, exact owners and closure. One fixed immutable directory prevents duplicate dispatch. Same CPU2/3,total200%,one thread,Tasks64,hard768MiBvirtual,1MiBstack,850MiBRAM/5GiBdisk minimum,180sservice+90sstop,16MiB output reservation and campaign checkpoint remain. No downloads.

PowerShell, ONLY after explicit maintenance-restart approval and a fresh census:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_xvf_restart_v2.py --maintenance-restart-approved --census <fresh-census.json>
```

CMD / Anaconda Prompt, same conditions and existing Python (no installation/activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_xvf_restart_v2.py --maintenance-restart-approved --census <fresh-census.json>
```

Prepared code and syntax validation are not execution or qualification. Before crediting: independently bind exact admitted hashes, single argv with final0, command receipt, firmware readbacks, natural unit exit, exact owner/hardware lease closure, original app/config/install and closed capture. A timeout/nonzero reply stays uncertain; never send the reset again as a retry. Actual quiet capture and live B01 need separate checks.
