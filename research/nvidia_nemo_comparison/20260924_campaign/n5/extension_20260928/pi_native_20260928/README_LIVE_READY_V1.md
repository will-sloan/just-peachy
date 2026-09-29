# Explicit quiet-route readiness v1

Purpose: prepare a bounded source-only XMOS I2S route check without changing the qualified B01/B05 previews. Native mock mode exercises the actual live-source and restoration logic with fake device/control input; it never opens ALSA or sends hardware controls. User mode is a distinct, explicit 12-second quiet microphone check. It loads no speech models, saves no audio, and does not qualify transcription, sound quality, microphone calibration, or speaker accuracy.

## Inputs and outputs

Inputs: exact qualified shared-app-b01-fir-v1 source, the unchanged current live_config.json and xvf_host hashes, a comprehensive host census newer than 15 minutes, fresh target owner/unit/RAM/disk checks. User mode additionally requires source-bound LIVE_READY_V1_QUALIFICATION.json and the physically ready person's --ready-now flag. Scheduled tasks must never supply that flag or invoke user mode.

Outputs remain private in local/n5/research-extension-20260928/pi-native-20260928/<run>-evidence and ~/JustPeachy/research/nemotron-20260928/<run>: admission, exact boot/PID/start ownership, service receipt and result. The quiet result contains counts, amplitude peak, source timing, route snapshots/restoration receipts and integrity flags, not audio. An independent review is required after every actual user run; qualification is not evidence that hardware ran successfully.

## Host commands (PowerShell)

Run from the campaign worktree. The existing Python environment is reused; no installation or download is needed.

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
# Use a fresh comprehensive census, not an expired example.
& $py -B "$p/launch_live_ready_v1.py" --mode mock --census <fresh-census.json>
# Only when physically ready, quiet, and qualification exists:
& $py -B "$p/launch_live_ready_v1.py" --mode user --ready-now --census <fresh-census.json>
```

CMD and Anaconda Prompt use the same existing interpreter (no conda activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928"
"%PY%" -B "%P%/launch_live_ready_v1.py" --mode mock --census <fresh-census.json>
rem Only while physically ready, quiet, and qualification exists:
"%PY%" -B "%P%/launch_live_ready_v1.py" --mode user --ready-now --census <fresh-census.json>
```

The mock run name is immutable; an existing attempt must not be overwritten or rerun. A repair needs fresh versioned files/admission. User run names are unique UTC timestamps. This command opens no visible GUI and plays nothing. Do not speak or begin a restaurant recording during this source-only check. A later explicitly ready spoken session will require its own protocol.

## Envelope and behavior

The shared research flock spans systemd completion; the existing hardware lease remains owned by the actual source until restoration and stream closure. Every dispatch rechecks recorded owners, units, source/config/install hashes, original app PID creation identity, closed capture, >=850 MiB available RAM and >=5 GiB disk. Host C/G minimums and the combined 1-GiB output allowance remain enforced. This path reserves 16 MiB new output. It does not alter the original app, autostart, OS settings, configuration or personal profiles.

CPUs 2/3, aggregate 200%, one native thread, TasksMax64, hard 768-MiB address space, 1-MiB startup stack, no GPU. Service maximum180 seconds plus90 seconds for stopping; each hardware control timeout is2 seconds in the private per-run configuration. Quiet source target12 seconds; missing callbacks/counts fail, and the source is stopped/restored in finally. SIGTERM requests the same cleanup. Two stop attempts are bounded; an error remains a failure even if retry closes it. Forced termination cannot prove hardware restoration; read the final receipt and actual state before any next use. No memory-cgroup or per-job swap guarantee is implied.

The mock protocol checks consent before lease, I2C O0/O1 selected channel/gain and 48k-to16k sample mapping, successful restoration, applied-write/lost-reply restoration, rejected firmware cleanup and retention of the hardware lease if a stream refuses closure. Fake device clocks and inputs do not qualify acoustic timing or real hardware. The actual FIR implementation is reused unchanged. No model workload is repeated here.

## Review

The independent reader must bind admission/files/result/dispatch receipt, verify six mock cases, natural exit and exact owner closure, then recheck original config/install/app and closed capture. A later real run must also review source counts/clock progression, ring loss, route readback, selected O0 gain, restoration and natural process/lease closure. Passing mocks is only permission-path readiness for an explicit quiet probe. B01 live model passage, sustained memory, physical screen/touch and consented real speech remain separate gates.
