# CM5 offline live prototype — deployed 2026-09-22

**Superseding motion/assembly update:** see [CM5_MOTION_3D_20260922.md](CM5_MOTION_3D_20260922.md)
for rc4. The user clarified that the sensor is NOT yet mounted in the enclosure;
compensation is inactive until the one-time mounting confirmation. The rc3
record below is historical, not evidence of current physical alignment.

Current release: **proto1-cm5-20260922-rc3**, installed, activated and observed
automatically launching/listening after a real reboot. Portrait transform 90,
live captions, relative-direction drawing and Stop are visible. Throttle 0x0.

Export: `G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-cm5-20260922-rc3.zip`.
SHA256: `b1ed2f81267623ba8fa9e9e1a1c1272b420989d488b8d134bbc37d226e0b56a1`.
229 payload files, 1,037,660 bytes. The archive is immutable. This post-deployment
receipt is outside it; runtime source is the matching versioned source.

## What changed

- XVF3800 onboard linear microphones retained. Matching 3.2.1 INT/lr48/lin/I2C
  image flashed via XTAG4; VERSION, BLD_MSG and topology checked on the Pi.
  Audio now uses the existing 40-pin I2S connection, control uses I2C; no XVF
  micro-USB connection is needed during operation.
- Existing Phase6/7/PROTO1 speech models, recipes, O0/O1 handling, personal
  enrollment, modes and profile storage reused. Windows USB transport retained.
- Saved microphone permission removes repeated prompts. Desktop autostart and
  one-shot listening on app launch enabled for this Pi. Stop remains available;
  failure does not create an automatic capture-retry loop. Windows saved
  microphone permission also updated without copying personal data to the Pi.
- Native BMI270 sensing added at I2C1/0x68, chip ID 0x24, rigid mounting confirmed
  by user. One bounded worker and Bosch SensorAPI; no extra inference/cloud work.
- Experimental, bounded relative yaw correction feeds the existing spatial
  modes and display. Pickup/tilt/uncertainty invalidates spatial trust. Voice
  identity and captions remain available. Settings exposes status, toggle/reset.

## Executed verification

| Check | Result |
|---|---|
| Full software suite | 345 passed, no failures/errors/skips |
| Release tools | 22 passed |
| Final changed-module checks | 47 passed |
| Native I2C/I2S capture + clean Stop | Passed; 10-second initial check |
| Concurrent XVF capture/telemetry + BMI270 | Passed; 60 seconds, 960160 model samples, no capture integrity or sensor error |
| BMI270 CPU during combined check | 0.208 CPU seconds over 60.1 seconds, ~0.35% of one core |
| Real native portrait auto-Start/Stop | Passed on rc2, 35.9-second bounded GUI check |
| Offline speech inference | Passed on rc2 in a network namespace with only loopback down; public 12-second CMU fixture, 15.72-second wall time including startup, STOPPED/error null |
| Final rc3 reboot | Auto-launched correct version, listening and producing live captions, portrait display, motion-assisted frame visible |

rc2→rc3 changes were limited to detecting horizontal acceleration using vector
deviation from gravity, and correcting hardware-status wording in Help. The
47 checks cover affected motion/spatial/UI paths. Capturing ambient speech is
not a measured recognition-accuracy or speaker-identification benchmark.

## Use and limitations

Power on normally and leave the unit still for two seconds for gyro calibration.
Ordinary runtime needs no internet, router, PC or XTAG. Ethernet remains useful
for maintenance. All model files and dependencies are installed locally.

Settings → **Motion sensor · relative direction** shows yaw and status. The
frame assumes speakers are in the initial front half-plane and supports small,
level in-place turns. It is not absolute yaw, reliable translation tracking,
or a drift-free room map. The linear microphone array remains front/back
ambiguous. Physical known-angle rotation with a stationary speaker is still
pending; compensation is clearly marked experimental. After pickup/relocation,
Reset positions and Apply assigned seats again. Existing people remain saved.

The XMOS evaluation board stops processing audio after eight hours of continuous
operation and requires restart; production-licensed devices do not have that
evaluation limit (XMOS user guide 3.2.1, printed page 1). No licence workaround
or timed firmware reset was introduced.

## Files and run commands

Site data: `/home/peachyprototype/JustPeachy/data`.
Install/model store: `/home/peachyprototype/JustPeachy/install`.
Autostart: `~/.config/autostart/just-peachy.desktop` uses the retained rc2
current-pointer launcher; it correctly selects current rc3 source/runtime.
XVF setup: `just-peachy-xvf-io.service` initializes vendor board level shifters.
Its output is bounded and requires no network. Working DSI setup is preserved.

Purpose, inputs/outputs, Windows PowerShell/CMD/Anaconda/Pi commands, firmware
rollback and hardware details: [CM5_I2S_MIGRATION.md](CM5_I2S_MIGRATION.md).
Sensor behavior/build/tests: [README_IMU.md](../app/README_IMU.md).
Native helper build: [README_NATIVE_XVF_USB_ARM64.md](../release_tools/README_NATIVE_XVF_USB_ARM64.md).

Evidence/receipt:
`G:\Just_Peachy_PROTO1\cm5_bringup_20260922\native_evidence\CM5_DEPLOYMENT_RECEIPT.json`.
Target evidence: `~/JustPeachy/checks/20260922`.
No large dataset sweep, model retraining, or private Windows profile transfer
was performed. Changes are saved locally; this turn did not push to GitHub.
