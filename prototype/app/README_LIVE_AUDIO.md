# Live audio modules

`live_audio.py` provides explicit-consent XVF3800 capture, the shared device lease, documented reversible routing, stereo O0/O1 selection, once-only live gain, timestamped streaming 48-to-16 kHz conversion and bounded gap reporting. `windows_audio.py` reads capture endpoint identities and three default playback roles without setting anything.

Inputs: the external `live_config.json`, explicit in-app microphone consent and the selected physical XVF. Outputs: 16 kHz mono `LiveBlock` objects and metadata/restoration receipts. No capture occurs just by importing or running inventory. `config/live.example.json` is a non-executable template until its null host/lease paths are configured.

The desktop's external live binding is `C:\Users\amiri\JustPeachy\data\live_config.json` (portable default `~/JustPeachy/data`). AppData is deliberately avoided because the packaged development host redirects it into host-specific private storage.

The live pipeline uses the first accepted block's PortAudio ADC/current-time difference to include input buffering when binding sample zero to `perf_counter`. WASAPI can deliver eleven 10 ms callback blocks together from one 110 ms host packet; subtracting only a callback block caused the reported startup failure. The fixed epoch is never rebased, and future-source timing guards remain enabled. Each block preserves the old monotonic timestamps and adds the high-resolution callback timestamp and PortAudio current time. Delayed reader delivery still contributes to measured source age.

If the driver timestamps are unusable, the source can use the reported stream input latency, explicitly recorded as `reported_input_latency_estimate` and `estimated_unqualified_for_latency_measurement`. Missing or too-short latency also fails clearly. Neither driver timing nor this fallback is calibrated acoustic-arrival latency. `source_started` and the bridge's `clock_metadata` record the selected method/confidence. Teardown keeps the original lane failure and records a later closed-journal error separately.

The regression tests below include burst delivery, driver-clock fallback, invalid timing rejection, and preservation of the original failure. They use fake capture and require no microphone or downloaded model execution. PortAudio defines the callback timestamp fields in its [stream documentation](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html); the [WASAPI source](https://github.com/PortAudio/portaudio/blob/master/src/hostapi/wasapi/pa_win_wasapi.c) and [buffer adapter](https://github.com/PortAudio/portaudio/blob/master/src/common/pa_process.c) explain the buffered callback behavior.

From the `prototype` directory, PowerShell:

```powershell
& '..\.edge-speech-env\python.exe' -m app.live_audio --output evidence/live_adapter/audio_inventory.json
& '..\.edge-speech-env\python.exe' -m unittest discover -s tests -p 'test_live*.py' -v
```

CMD/Anaconda Prompt:

```bat
"..\.edge-speech-env\python.exe" -m app.live_audio --output evidence\live_adapter\audio_inventory.json
"..\.edge-speech-env\python.exe" -m unittest discover -s tests -p "test_live*.py" -v
```

See [the full live adapter guide](../docs/LIVE_AUDIO.md) for the exact working-directory command, control inventory, interface, startup/stop sequence, physical evidence limitations and live human checklist. Use the root application's documented launcher for microphone capture; the inventory command never captures speech.

`beam_diagnostics.py` adds an optional read-only display of the hardware's recent
beam angles. Its bounded worker begins only within a consented, routed live
session. In the two experimental spatial modes, the bounded `live_spatial.py`
adapter also delivers causal cues to the existing tracker. Enrollment and ASR
endpointing remain unchanged. See [the spatial adapter guide](README_SPATIAL.md).
Open Settings → Beam angles
while the app is running. See [Beam diagnostics](../docs/BEAM_DIAGNOSTICS.md) for
the inputs, outputs, lifecycle, angle limitations, and exact PowerShell and
CMD/Anaconda launch and model-free test commands.
