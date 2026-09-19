# Live audio modules

`live_audio.py` provides explicit-consent XVF3800 capture, the shared device lease, documented reversible routing, stereo O0/O1 selection, once-only live gain, timestamped streaming 48-to-16 kHz conversion and bounded gap reporting. `windows_audio.py` reads capture endpoint identities and three default playback roles without setting anything.

Inputs: the external `live_config.json`, explicit in-app microphone consent and the selected physical XVF. Outputs: 16 kHz mono `LiveBlock` objects and metadata/restoration receipts. No capture occurs just by importing or running inventory. `config/live.example.json` is a non-executable template until its null host/lease paths are configured.

The desktop's external live binding is `C:\Users\amiri\JustPeachy\data\live_config.json` (portable default `~/JustPeachy/data`). AppData is deliberately avoided because the packaged development host redirects it into host-specific private storage.

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
