# CM5 offline prototype: linear XVF3800, I2S audio and I2C control

Purpose: run the existing Phase 6/7/PROTO1 models, modes, enrollment and live
spatial telemetry on the assembled CM5, without the XVF micro-USB connection.
This is a transport/deployment change, not a new research or tuning study.

## Hardware and firmware

Target: Raspberry Pi OS Bookworm 64-bit, CM5 IO board, XK-VOICE-SQ66/JGB0084
1V1 with the onboard **linear** microphone configuration. Firmware 3.2.1:
`application_xvf3800_intdev-lr48-lin-i2c.xe`, SHA256
`af9d09a7328547778d02203b81c63b9aeef31dcc8138593347f21e2deee1323e`.
This selects 48 kHz I2S, internal clock recovery, I2C control and linear
microphones. Do not substitute squarecular, external-MCLK or spatial-rendering
firmware. Spatial telemetry is available without the spatial-rendering image.

XTAG4 connects to the Windows setup computer over its own USB and to the
XVF board's **XSYS2** debug connector using its supplied ribbon cable. It is
only needed for programming. Normal operation uses the existing 40-pin cable.
Power off before changing physical connections.

Physical header pins (not BCM numbering):

| Function | Physical pins | Direction |
|---|---|---|
| Board power | 2 or 4 (+5V), suitable GND | CM5IO to board |
| I2C SDA / SCL | 3 / 5 | Shared control bus |
| I2S bit clock / word clock | 12 / 35 | CM5 to XVF |
| Processed stereo capture | 38 (GPIO20) | XVF to CM5 |
| Reference audio | 40 (GPIO21) | CM5 to XVF; no playback used here |

Header orientation must preserve pin numbers end to end. The screen retains
its separate 5V/GND lead and correct DSI **display** cable on CAM/DISP0. It
does not need the XVF audio interface to display. User confirmed portrait
orientation and touch after replacing the incorrect camera cable.

The XMOS user guide 3.2.1 section 2.3.3 and programming guide table 2.1 specify
INT operation as an I2S slave with I2C/SPI control; UA firmware instead uses
USB control and drives I2S clocks. **Load INT firmware before enabling Pi
master clocks/level shifters. Disable the Pi I2S setup before restoring UA.**
Source: https://www.xmos.com/documentation/XM-014888-PC/html/doc/user_guide/index.html
Board pin mapping: JGB0084-SCHEMATIC-1V1-C, sheet 4.

## Programming from Windows

Inputs already prepared under
`G:\Just_Peachy_PROTO1\cm5_bringup_20260922\firmware`: the INT image,
original vendor UA image for rollback and `firmware-receipt.json`.
No existing device flash contents were dumped; rollback is the matched vendor
UA 3.2.1 linear image, not a backup of unknown custom flash contents.

CMD / Anaconda Prompt (no Conda activation needed):

```bat
call "C:\Program Files\XMOS\XTC\15.3.1\SetEnv.bat"
xflash -l
xflash --id 0 "G:\Just_Peachy_PROTO1\cm5_bringup_20260922\firmware\application_xvf3800_intdev-lr48-lin-i2c.xe"
```

Only use ID 0 when the listing shows the intended single board. PowerShell:

```powershell
cmd.exe /d /c 'call "C:\Program Files\XMOS\XTC\15.3.1\SetEnv.bat" && xflash -l'
cmd.exe /d /c 'call "C:\Program Files\XMOS\XTC\15.3.1\SetEnv.bat" && xflash --id 0 "G:\Just_Peachy_PROTO1\cm5_bringup_20260922\firmware\application_xvf3800_intdev-lr48-lin-i2c.xe"'
```

Output is the xflash completion log. Follow it with actual firmware/build,
microphone topology, audio and beam readbacks; successful flashing alone is
not live qualification. UA rollback image SHA256:
`ead1ba7419c99687ab6806b00803564967eab8acb7278d66d663cb42be070b08`.

## Pi interface setup

Vendor source: https://github.com/xmos/vocalfusion-rpi-setup at
`82b6c21e6d5f302eca5b9a747a3c16e89ae4187a` (supports Pi5/CM5).
Use its `overlays/xmos-device.dts` and `setup_io_exp_and_dac.py` unchanged.
The complete vendor setup script is not needed: it also changes default ALSA
configuration, enables SPI and replaces the user's crontab.

Build/install the overlay with dtc. Preserve the working DSI configuration,
then enable `dtparam=i2c_arm=on`, `dtparam=i2c_arm_baudrate=100000`,
`dtparam=i2s=on` and `dtoverlay=xmos-device`. Load `i2c-dev`.
The vendor IO-expander initialization for `xvf3800-intdev` writes PCAL6408A
address **0x20**, registers 0x01=0x79, 0x03=0x1F and 0x45=0xFD. It enables
the board's I2S level shifters without external MCLK or DAC reprogramming.
Run at each boot before opening audio. Firmware control is address **0x2C**
on `/dev/i2c-1`, with the normal user in group `i2c`.

Native build steps and inputs/outputs:
`../release_tools/README_NATIVE_XVF_USB_ARM64.md`. The generated ARM64
`xvf_host`, USB/I2C shared libraries and 3.2.1 command map stay together at
`~/JustPeachy/tools/native_xvf_usb/bin`. ARM32 vendor binaries do not run
natively in this ARM64 installation.

Enumerate `arecord -l` and sounddevice devices after reboot. Bind the exact
`XMOSDevice ... (hw:N,D)` **capture** name in external `data/live_config.json`;
do not guess device 0/1, use the default microphone or change system speakers.
Set `control_protocol: "i2c"`, `hostapi: "ALSA"`, `expected_array_type: 1`,
`native_rate: 48000`, `tap: "O0"` and the absolute native helper path.
The adapter verifies firmware 3.2.1, linear topology and four microphones,
primes input clocks, applies the existing O0/O1 routes, then verifies them.
O0 receives +3dB once; O1 is unity. Existing 16k model input and spatial methods
are retained. Stop restores owned settings while clocks are still running.

## Saved microphone permission and offline startup

The user explicitly requested permanent microphone permission. The external
settings keys are `microphone_preapproved: true` and optionally
`auto_start_listening: true`. Both must be JSON booleans. Settings exposes
**Microphone: Always allowed** and **Listen when app opens: On/Off**.
Saved permission removes the repeated Start prompt. Stop remains available;
automatic listening makes one attempt per app launch, never a retry loop.
File replay with `--wav` never automatically opens the microphone.

The normal desktop login starts the portrait GUI using a desktop autostart
entry. It requires no network-online service, cloud account or internet call.
All eight models and 13 pinned ARM64 wheels are already local; no model
download or package installation happens during ordinary startup.
People/profiles/settings remain outside immutable releases.

Manual launch on Pi (current-pointer launcher also works after a later update):

```bash
python3.11 "$HOME/JustPeachy/install/releases/proto1-cm5-20260922-rc2/release_tools/launch_current.py" \
  --root "$HOME/JustPeachy/install" --data-root "$HOME/JustPeachy/data" -- --fullscreen
```

Window launch on Windows: `prototype/Start-Prototype.cmd` or, in PowerShell,
`& .\prototype\Start-Prototype.ps1`. Existing USB settings remain compatible;
this CM5's INT firmware must be changed back to UA before Windows USB capture.

## Verification and current status

64 focused Windows software checks passed (UI, live adapter, controller views,
lifecycle). These use mock hardware and validate saved consent, one-shot
startup, cancellation/Stop, USB compatibility and explicit I2C routing.
Native ARM64 host/helper/map build passed with all shared libraries resolved.
See `CM5_INSTALL_20260922.md` for actual flashing, offline inference, physical
audio and boot results. Pending checks are not implied by these software tests.

Run the focused checks in PowerShell from the repository root:

```powershell
$env:PYTHONPATH="$PWD;$PWD\prototype;$PWD\prototype\vendor;$PWD\prototype\tests"
& .\.edge-speech-env\python.exe -m unittest test_ui test_live_audio test_controller_views test_lifecycle -q
```

CMD / Anaconda Prompt:

```bat
set PYTHONPATH=%CD%;%CD%\prototype;%CD%\prototype\vendor;%CD%\prototype\tests
".edge-speech-env\python.exe" -m unittest test_ui test_live_audio test_controller_views test_lifecycle -q
```

Inputs: source and synthetic test fixtures. Outputs: test status; no real
microphone capture or model inference. Local deployment receipts and logs:
`G:\Just_Peachy_PROTO1\cm5_bringup_20260922\native_evidence` and
`~/JustPeachy/checks/20260922`.
