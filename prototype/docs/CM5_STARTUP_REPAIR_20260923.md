# CM5 automatic startup repair — 23 September 2026

Release: `proto1-cm5-20260923-rc5`.

The desktop autostart entry was executing, but the application refused to start
because `~/JustPeachy/data/runtime.lock` still named PID 28763 from the previous
session. Ethernet was unrelated to that failure. The previous record was saved
under `~/JustPeachy/install/inbox/startup-rc5/old-runtime-lock.json`.

The app and release updater now share an OS-held ownership guard, preserve
active/uncertain owners, and recover proven stale Linux records after process
death or a different boot. Metadata publication is atomic. The guard remains
held for the owner's lifetime. No time-based expiry or session/profile deletion
is involved. Windows retains conservative handling of legacy stale records.

A visible **Just Peachy** desktop shortcut and `~/JustPeachy/start-prototype.sh`
now start the activated release. The same shell launcher is installed in desktop
autostart. It uses local models and does not wait for a network connection.
Output goes to `~/JustPeachy/startup.log`. See
`../release_tools/README_STARTUP.md` for installation, manual launch and test
commands for Pi, PowerShell, CMD and Anaconda Prompt.

Checks performed:

- Windows application suite: 361 tests, zero failures/errors; two Linux-only
  tests skipped. Release/ownership focused suite: 26 tests, zero failures/errors.
- All four ownership tests passed on the actual Pi, including an unclean child
  process exit, concurrent contenders and a previous-boot record with reused PID.
- Offline installation verified 235 release files, local model hashes and ARM64
  dependency imports. Archive SHA256:
  `a41c218193fe9344afbc420f9a5afe238e194f9f2c2b2fdca4a1e47cd974daf8`.
- Real GUI started using a systemd `PrivateNetwork=yes` test service; screenshot
  showed **Microphone listening**, active Stop button and fresh XVF beam telemetry.
  Network isolation preserved SSH to the host while withholding app networking.

- Actual Pi reboot passed: a new boot ID and app PID 1128 were observed. Desktop
  autostart opened the portrait GUI, began XVF listening, displayed fresh beam
  evidence and produced live captions without manual launch. The startup log was
  empty (no reported startup errors). The board I/O service was active.

Evidence: `G:\Just_Peachy_PROTO1\cm5_bringup_20260922\startup_rc5_checks`,
`offline-startup-rc5.png`, `reboot-startup-rc5.png`, and
`reboot-verification-rc5.json` in that bring-up directory. Linux lock checks also
remain runnable under the Pi's `~/JustPeachy/install/inbox/startup-rc5/` directory.

The final physical power-bank/Ethernet-unplugged test remains a user acceptance
check: stop listening, shut down the Pi normally, remove Ethernet, connect the
power bank, and check that the app opens and displays captions. Shutdown avoids
unnecessary filesystem/session damage; crash recovery is not a substitute for
flushing saved data. Startup is verified, not a new prolonged-session assessment.
No speech-model, enrollment, spatial algorithm or hardware configuration change
was made. The loose BMI270 remains `fixed_mount=false` pending enclosure assembly.
