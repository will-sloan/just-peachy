# XVF live input adapter

`app/live_audio.py` owns one explicitly selected XVF3800 input stream and the existing project device lease. `app/windows_audio.py` only reads Windows capture endpoint IDs and default playback IDs. No module opens a microphone on import or inventory. Starting requires explicit in-app consent.

## Run and inputs

From PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype'
& '..\.edge-speech-env\python.exe' -m app.live_audio --output evidence/live_adapter/audio_inventory.json
& '..\.edge-speech-env\python.exe' -m app.live_audio --config evidence/live_adapter/LOCAL_DEVICE_CONFIG.json --output evidence/live_adapter/readonly_device_inventory.json
& '..\.edge-speech-env\python.exe' -m unittest discover -s tests -p 'test_live*.py' -v
```

From CMD or Anaconda Prompt (the explicit interpreter avoids modifying an active Conda environment):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
"..\.edge-speech-env\python.exe" -m app.live_audio --output evidence\live_adapter\audio_inventory.json
"..\.edge-speech-env\python.exe" -m app.live_audio --config evidence\live_adapter\LOCAL_DEVICE_CONFIG.json --output evidence\live_adapter\readonly_device_inventory.json
"..\.edge-speech-env\python.exe" -m unittest discover -s tests -p "test_live*.py" -v
```

The optional site JSON supplies `host_executable`, `lease_path`, `endpoint_name`, `endpoint_id`, `hostapi`, and `tap`. It binds this desktop's installed matching vendor tool and existing `measurement_app/hardware.lock`; those machine paths belong in local configuration, not portable source. Linux supplies its installed matching ARM64 host tool and shared local lease through the same schema. The Windows binary is not an ARM64 binary. Tests use simulated control/stream objects and do not open microphones.

This desktop's ready site binding is `%USERPROFILE%\JustPeachy\data\live_config.json` (`C:\Users\amiri\JustPeachy\data\live_config.json` on this desktop). The root app reads it and supplies each session's tap and evidence directory. User-profile storage avoids the observed packaged-host virtualization of AppData; a native file-handle check confirmed this path resolves directly to the same physical file. Linux defaults to `~/JustPeachy/data`. Explicit application data/model overrides remain available. `config/live.example.json` is a portable template: its null host/lease values intentionally refuse startup until configured. Set Linux `host_executable` to the matching installed native tool, `lease_path` to a shared external writable lock, and select the enumerated physical ALSA endpoint. For Windows use the installed Windows host plus the existing research lease and `Windows WASAPI`; do not copy a historical integer index. Reconnecting through a different USB port can require deliberate endpoint ID selection.

Outputs are read-only inventory JSON and unittest results. USB reads sometimes require an active audio loop: idle firmware may report that the audio loop is inactive. Inventory stops DSP reads after that response, records the limitation, and never opens a stream to work around it.

## Application interface

Construct `LiveConfig(**site_json)` and `XVFLiveSource(config, status_callback=callback)`. `start(consent=True)` returns actual route/endpoint metadata. Call `read(timeout=.25)` from a dedicated producer thread. Each `LiveBlock` carries float32 mono 16 kHz audio, model sample origin, native frame origin/count, callback/ADC/delivery timestamps, fixed FIR delay and observed host delivery lag. `None` means timeout or completed; consult `status()['finished']`. `LiveGap` means the admitted session is incomplete. Stop it and start a new recognizer/association epoch after explicit reconnect. `stop()`/`finish()` are idempotent and return restoration/default-output observations. `wait(timeout)` waits for stop completion.

After stop, `summarize_live_integrity(source)` provides the authoritative `ok` gate and `reasons`, drop/fault counters, restoration issues, actual route/device/rate metadata, and unconsumed tail count. Enrollment must check it even if its read loop raised no exception: a callback overflow can occur while its consumer analyzes quality. The deliberately unconsumed stop tail cannot count toward saved speech.

The bridge binds a fixed epoch using the first callback's high-resolution host
time and valid PortAudio ADC/current-time difference. Buffered Windows packets
retain their input age. When driver timestamps are unusable, reported input
latency is explicitly recorded as an estimate, unqualified for acoustic latency
measurement. Missing usable timing fails. Queue lag is not hidden by resetting
the epoch at consumer delivery. See [Windows live verification](WINDOWS_LIVE_FIX.md).

Never silently reconnect to another microphone. The adapter resolves the selected endpoint on each start; it does not retain the prior PortAudio index. On Windows it also matches the Core Audio endpoint ID. Two XVF boards are refused because this matching vendor USB control tool does not provide a safe serial-address selector. A changed ID needs deliberate selection. Only one project lease owner can control/capture the device.

## Signal path and start/stop

The bound v3.2.1 UA `io48` firmware uses 48 kHz stereo input-only capture. WASAPI requests exclusive capture and disables automatic conversion. No render stream, default audio setter, volume API, driver modification, firmware flash, geometry change, or USB-bit-depth setter exists here. Other PC microphones and speakers can remain connected.

The consented input stream first supplies the USB clock while its callback discards all priming samples. Device settings are read before setters. Then only changed route controls are written/read back: packed substitute input off, packed output off, documented microphone gain 10 and system delay -32, ASR output enabled, both 16-to-48 kHz upsamplers on, left category 7/source 3 (automatic ASR O0), right category 6/source 3 (processed automatic O1). The gain/delay baseline comes from XMOS v3.2.1 product `control_param_values.yaml`; it is not a fresh room calibration. Other DSP settings and reference gain are preserved. Category 7 is not accepted as ASR unless ASR mode is enabled.

Device ASR gain must read 1.0 or startup fails before route setters. The O0 host adapter applies +3 dB exactly once, after demultiplexing/resampling; O1 is unity. Historical prepared O0 WAVs already contain gain and must use the separate unity file adapter. The 97-tap anti-alias FIR has a declared 1 ms group delay and continuous filter/decimation phase across callback blocks. Native/converted clocks stay explicit; ADC times are not calibrated acoustic-arrival times.

Callbacks copy into a preallocated raw ring (default 10 s, 3.84 MB stereo float32) and update bounded counters. No file, GUI, model or device-control work runs there. Filtering runs in `read()`. The larger application history ring is separate. On callback overflow, unexpected size, stream termination or a two-second callback stall, the adapter reports a gap rather than substituting a mic or claiming unlimited lossless capture. Enrollment must fail safely on a gap.

Stop first disables admission, restores only owned route changes while the input clock is still active, closes the stream and releases the lease. It does not overwrite an externally changed parameter. Disconnect or restore failure is explicit in the receipt; it never starts a render stream to force restoration. Pending route restoration must be reviewed before the next session. New device/session temporal state starts fresh; personal people are outside this adapter and stay intact. Evaluation firmware's eight-hour limit requires a safe restart between sessions; the adapter never resets mid-utterance.

If PortAudio remains active after a failed stop/close, Stop raises and retains
the hardware lease; retry cleanup before another session can start. Such a
retry cannot turn the interrupted capture into a clean integrity pass.
Enrollment Discard surfaces restoration/close failure instead of hiding it.
Save/Discard release temporary capture rings and quality vectors only after
the capture and quality workers have ended; a failed store commit retains the
reference for retry. Metadata-only receipts remain available for diagnosis.
If enrollment setup fails after opening capture, the controller stops the
source and wakes/joins the quality worker; unresolved active owners block
replacement. Focused fake-device regression commands are in
`tests/README.md` under “Enrollment shutdown and temporary-data cleanup”.

## Evidence and pending human check

The tests cover consent before access, lease exclusion, changing indices, ambiguous/missing device rejection, failed partial writes and safe restoration, external setting preservation, once-only gain/stereo demux, overflow, unplug/stall state, resampler phase/anti-aliasing, and read-only output comparison. Tests are not physical mic/speech verification.

Desktop inventory identifies XVF firmware 3.2.1, `ua-io48-lin`, USB16/16 and one
XVF capture endpoint. Version 0.1.3 passed bounded physical input/native inference
checks with both Fast and Balanced recipes, zero dropped frames and restored
routing; see the linked receipt. Human speech/enrollment accuracy, unplug/replug
and sustained live operation still require separate checks. DSP reads can fail
while the USB audio loop is inactive; no render stream is added to work around it.

In the live app: press Start, read the exact device and consent, speak, inspect captions, Stop, then review the route/default-output receipt. For disconnect recovery, unplug while listening, verify an explicit gap, reconnect and explicitly Start a new epoch. Windows default-output IDs are read before/after; a changed ID alone does not identify its cause.
