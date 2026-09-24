# Bounded CM5 capture check

`check_cm5_live.py` consumes 1–90 seconds of explicitly authorized live XVF
input through the real adapter, then stops/restores the route. It saves only
signal statistics, beam telemetry and integrity metadata, not a WAV. It does
not run speech models, change firmware, or prove recognition quality.

Optional `--imu-config PATH` starts the configured BMI270 worker concurrently
and stores one motion snapshot per second for shared-bus/CPU and movement
checks. The same run stops both workers; no voice audio is saved. Use 60–90
seconds only when testing a deliberate physical rotation or pickup/reset.

The JSON now includes `motion_ok`; a requested IMU check fails its exit status
unless its final sampled pose is valid and no worker error was observed.
A temporary mounted test configuration can test software/sensor execution,
but MUST NOT be reported as a physical mounting or known-angle qualification.
The September22 motion3d runs preceded the user's clarification that the
boards are still unassembled. The installed site configuration therefore
keeps `fixed_mount=false`; native XVF directions remain available.

Inputs: an installed/candidate source directory, validated external
`live_config.json`, duration and a new output JSON. Outputs: JSON and the
normal device restoration receipt under the configured evidence directory.
Use only when the device is free and microphone use is authorized.

On the Pi, with this deployment's local Python:

```bash
~/JustPeachy/install/runtimes/proto1-cm5-20260922-rc1/bin/python check_cm5_live.py \
  --source ~/JustPeachy/checks/20260922/candidate-app \
  --config ~/JustPeachy/checks/20260922/candidate-live.json \
  --output ~/JustPeachy/checks/20260922/i2c-live-check.json --seconds 10
```

From Windows PowerShell or CMD/Anaconda, use `scp.exe -i KEY script USER@HOST:PATH`
to copy the script, then `ssh.exe -i KEY USER@HOST` and enter the Pi command.
No Conda activation is required. Use the verified host and SSH key documented
in `../docs/CM5_I2S_MIGRATION.md` and `CM5_FIRST_BOOT_WINDOWS.md`.

`check_cm5_gui.py` is a separate native acceptance harness. Inputs are an
immutable `--release`, external test `--data-root` with site live/IMU configs
and saved microphone permission/automatic listening, shared `--models`, and
`--output JSON`. It opens the real portrait UI and live pipeline, shows the
Motion page at 18 seconds, invokes the normal Stop control at 35 seconds,
waits for closure and closes the app. It preserves runtime/UI code unchanged.
Do not run alongside another capture owner. The existing application session
retention policy applies to this test data root; real transcript text may exist
there, though the output JSON contains status/metrics rather than caption text.

Run on the Pi using its installed runtime Python:

```bash
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 \
  ~/JustPeachy/install/runtimes/proto1-cm5-20260922-rc2/bin/python check_cm5_gui.py \
  --release ~/JustPeachy/install/releases/proto1-cm5-20260922-rc2 \
  --data-root ~/JustPeachy/checks/20260922/gui-rc2-data \
  --models ~/JustPeachy/install/models \
  --output ~/JustPeachy/checks/20260922/gui-rc2-result.json
```

Windows PowerShell/CMD/Anaconda: transfer and SSH as above, then run the Pi
command. The harness is not the ordinary startup launcher.
