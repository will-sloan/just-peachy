# Conditional XVF recovery under autonomous Pi authority

Purpose: address the retained source-quiet-v1 failure, where AEC_MIC_ARRAY_TYPE returned255 after the real PortAudio stream started, while VERSION/build remained readable. The earlier single maintenance restart followed by a fresh quiet source check provides a concrete recovery precedent. This does not establish an evaluation timeout or authorize a periodic reset. The September29 autonomous Pi authorization supersedes old per-restart readiness assumptions; the old launchers remain immutable and are not invoked.

Inputs: fresh WINDOW_V5 host census, original exact boot/PID/start identities, closed capture/research owners and free hardware/research leases; hash-bound original xvf_host, live configuration/install manifest, retained actual-stream failure and earlier restart receipts. Current VERSION/build must match3.2.1/intdev-lr48-lin-i2c. The new worker reads AEC_MIC_ARRAY_TYPE once with capture closed. A readable result skips the restart. An exact255 Resource-could-not-respond reply, combined with the bound earlier failure with an active stream, permits one literal `xvf_host -u i2c TEST_CORE_BURN 0`. Other errors/timeouts stop the operation. The current closed-loop query alone is not processing or audio-path proof.

Before any maintenance send, byte-identical tool/config/install backups are verified on both Pi and host. File restoration would use those verified copies; this operation does not alter those files. Firmware restart clears volatile DSP/adaptive state: unreadable pre-restart state cannot be backed up or claimed restored. A later source test must take a fresh readable post-restart routing snapshot and restore that snapshot. Neither firmware readback nor command exit0 proves the microphone path works.

Persist exclusive intent before the single command. Every command has a2-second timeout and a private receipt. A timeout/nonzero maintenance outcome remains uncertain/failed and is never retried. After a successful send, wait2seconds and read only VERSION/build. At most6 reads and1 maintenance command occur; no capture, playback, model, Pi reboot, firmware flash, OS/boot/swap change, training or download. All hardware commands execute under the existing hardware lease while the gate retains the research lease. Exact main/gate owners and actual live systemd properties are retained.

Resource envelope: CPUs2/3,total200%,Tasks64,hard768MiB virtual memory,1MiB stack,GPUoff;initial available850MiB and fixed32GBPi disk free5GiB plus reservation. Service300s/alarm290s/Stop10s; command timeout2s. Sampled owned RSS640MiB/availableRAM192MiB stops, not hard aggregate RAM enforcement.16MiB combined output reservation,8MiB target/8MiB host,8MiB per-file hard limit; JSON receipts128KiB, tool size below2MiB, command output postcondition64KiB. Kernel lacks MEMCG; global swap is contextual only. All existing usage and reservations remain counted.

Outputs: private xvf-recovery-v3 admission, pre-maintenance verified tool/config/install copies, host backup acknowledgment, current readback receipts, optional RESTART_INTENT and exactly one maintenance receipt, post-firmware readbacks, owner/envelope/resource/closure results. No audio is produced. Independently review command count/argv/chronology/outcome and hash-back up target receipts before a new source admission. Do not rerun this fixed ID or change its sources after dispatch.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/xvf_recovery_dispatch_v3.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V109.json
```

CMD / Anaconda Prompt (explicit interpreter; no activation needed):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\xvf_recovery_dispatch_v3.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V109.json
```

Use a fresh unused census younger than15minutes. Coordinator/census CPU14 applies before file reads. Worker/gate flags are internal to the admission. The code refuses existing output paths, active owners, wrong identities/hashes/limits, insufficient storage or checkpoint overlap. A successful maintenance receipt is only a firmware/control milestone; isolated actual source passage and combined B01 remain separate gates.
