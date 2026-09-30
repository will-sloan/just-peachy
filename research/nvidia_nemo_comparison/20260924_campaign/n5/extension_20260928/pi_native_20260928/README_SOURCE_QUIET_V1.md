# Actual isolated quiet microphone source

Purpose: qualify actual PortAudio startup/memory and the separate-process source facade, exact ordered source/IPC mapping, a deliberately paused consumer, accepted-tail Stop/drain, bounded reopenable PCM and route restoration. This fresh diagnostic uses September29 autonomous quiet authority, not an old ready-now launcher. No ASR, diarizer, GUI, playback or quality scoring. A source-only pass cannot establish combined B01 live readiness or repair the earlier input overflow under model load.

Inputs: immutable b01-quiet-artifact-v1/prototype (actual 97-tap NumPy FIR and detailed callback faults), the actual installed live_config.json, process-local alsa_hw_only_v1.conf and AUTONOMOUS_QUIET_AUTHORIZATION_V1.json. Explicit XMOS I2S hw:2,1 / ALSA / I2C / O0 / 48k route; no system/default audio changes. Original config and install manifest are copied and hash-checked before capture. The actual hardware lease and shared research flock remain mandatory. The source saves and fsyncs the full readable route snapshot before returning from the initial snapshot to any setters; original changed-key restoration runs while the clock and hardware lease remain owned. A second full readback must equal that snapshot before stream close. Unsupported or externally changed settings fail explicitly. The original app/files remain untouched; firmware reset is not performed.

New source_quiet_factory_v1 starts the real source in a fresh child. TransportV3 changes the fake-qualified V2 child envelope to256MiB/90s for actual NumPy/PortAudio; SIGALRM/SIGTERM are handled through source cleanup. The service allows60s Stop cleanup. FacadeV2 allows45s startup and otherwise retains the qualified ordered terminal-ACK interface. BridgeV2 verifies PortAudio's closed property after close (querying active on a destroyed stream is invalid). All derivatives preserve prior bound sources. The original controller has not been integrated.

Protocol: request Stop after192000 accepted16k samples (12s); retain every accepted queued sample until terminal ACK/natural child exit. Hard retained limit320000 samples (20s); capture-phase wall bound20s plus45s Stop/drain. After80000 samples the parent pauses200ms once, while the child continues the real callback/FIR/IPC route; queue bounds64blocks/65536encoded bytes and1s backpressure timeout remain. Metadata retain native/model offsets, epoch, ADC/current/callback/delivery/IPC clocks and priming. These clocks are not acoustically calibrated. New quiet/background audio remains private; its presence is not labelled silence.

Outputs: private source-quiet-v1 admission/config/install backups, PRE/POST_ROUTE_SNAPSHOT, SOURCE_START, raw float32 microphone prefix, mono16kPCM16 microphone.wav, bounded per-block TRACE, source Stop/Close/terminal receipts, exact owners and actual service envelope. WAV rounding/clipping is recorded; an independent reader must verify counts, float-to-PCM values, hashes, chronology, restoration, output bounds and closure before acceptance. Failed prefixes and all failures stay preserved.

Envelope: WINDOW_V5 target-inclusive32MiB combined reservation (16MiB target/16MiB host backup),52GiB payload including target and2.5GiB reservations,5GiB output window. Fixed32GB device retains5GiB free; C50GiB/G75GiB floors. Main768MiB/child256MiB hard virtual,1MiB stacks,CPU2/3,total200%,Tasks64,one numerical thread/GPUoff. Initial RAM850MiB; sampled aggregate640MiB RSS/192MiB available guard is not hard RSS enforcement. Main300s/290s alarm,60s service Stop; per-file8MiB. No OS/boot/swap change. Bounded signal cleanup is reviewed, not crash-proof restoration proof.

PowerShell (fresh unused census under15minutes required):
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/source_quiet_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V94.json
```

CMD / Anaconda Prompt (no download/environment activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\source_quiet_dispatch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V94.json
```

The facade, transport, factory, bridge, envelope and protocol are imported/internal admitted entry points, not general-purpose launchers. Fixed run roots refuse overwrites. Do not rerun a closed admission. Stop by October1 17:47:34UTC; independently review, back up all private files with hashes, and preserve the result even if failed.
