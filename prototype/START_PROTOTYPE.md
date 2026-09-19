# Start the live portrait prototype

The same application supports an XVF3800 connected directly to this Windows
desktop or to the future Raspberry Pi. Windows does not require a Pi. This is
a native desktop window; a browser is not required. Linux needs its own native
dependencies, device configuration, and verified ARM64 XMOS control tool.

After updating the source, close the old GUI and reopen the launcher below.
Windows' default microphone setting does not choose this app's source: the app
checks the explicit XVF endpoint in `live_config.json`. **Start** streams audio
into live inference; it does not automatically save a recording WAV. Use
Settings → Beam diagnostics for device beam arrows during an active session.

On this desktop, double-click `Start-Prototype.cmd` in this folder. The portrait
application opens at480×800 client pixels with the microphone off. Start asks
for microphone consent. Stop releases capture. PC speakers/headphones can stay
connected; the application uses no playback/render stream and changes no
Windows default playback endpoint.

PowerShell from the repository directory:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD/Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Direct Python in PowerShell:

```powershell
& .\.edge-speech-env\python.exe .\prototype\main.py gui
```

For a prepared file (no microphone):

```powershell
& .\.edge-speech-env\python.exe .\prototype\main.py gui --wav "G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav" --recipe balanced --mode anonymous_conversation
```

In CMD/Anaconda use the same command without the leading `&` and with normal
Windows paths. Inputs must be prepared mono16k PCM16 WAVs. Existing prepared O0
already has its +3dB applied, so file replay consumes it at unity.

For file replay, select the matching tap before loading the WAV. Known O0/O1
filenames are checked against that selection. Changing taps during replay is
rejected: Stop, choose the other tap, and load its actual prepared WAV. An
arbitrary filename still requires your explicit declaration of the prepared tap.

For live input, the external `live_config.json` under the personal data root
binds the matched XVF host tools, shared hardware lease, and stable endpoint
identity. See `docs/LIVE_AUDIO.md`. Never select a PC microphone as a substitute.
XVF ordinary live routing is applied only after consent and restored at Stop.

People → Add person asks for a name, consent and a15/30/60-second usable-speech
goal. A touch keyboard is provided. Read the paragraph, continue speaking if
needed, Stop, inspect quality, then Save. Test with different new speech in
Enrolled names or Open with names. Names/vectors remain outside the release.

Live paragraph verification awaits the user's availability. Automated file
tests are not proof that a real personal enrollment works acoustically in this
room. Follow `docs/ENROLLMENT_GUIDE.md` for the remaining interactive check.

Modes, recipe and tap are separate. Switching safely finishes pending words and
starts a new audio/identity epoch. Caption-only stops optional speaker inference;
previously loaded speaker weights may remain resident for a later switch.
Strict selected focus is experimental; use Show all whenever words seem missing.

Linux/CM5 launch after installing verified dependencies/assets:

```sh
python3 main.py gui --fullscreen --data-root "$HOME/JustPeachy/data" --models "$HOME/JustPeachy/shared/models"
```

Do not copy a Windows virtual environment to Linux. CM5 hardware execution,
touch/display drivers, camera and BMI270 wiring are pending. Use the checked
release/update/rollback workflow in `docs/PI_DEPLOYMENT_WORKFLOW.md`.
