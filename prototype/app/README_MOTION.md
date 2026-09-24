# Optional motion safety interface — task08

**Current CM5 implementation:** see [README_IMU.md](README_IMU.md) for the
live BMI270 driver, guarded relative rotation, GUI, actual hardware results,
configuration and commands. The task08 record below describes the earlier
sensor-free contract; its pending-driver statements are historical.

Purpose: connect a future verified motion adapter to existing assigned-seat
invalidation. There is no BMI270/GPIO/camera driver, background polling, inertial
navigation, absolute yaw or automatic re-anchoring in this release. Disabled
peripherals do not prevent Windows GUI or headless file replay.

`MotionEvent` inputs: stationary/moving/settling, integer source and receipt
timestamps mapped to the host's `time.monotonic_ns()` clock, quality 0..1,
explicit simulated provenance, and translation/range uncertainty. Reject
unmapped clocks, future times and invalid values; ignore duplicate/out-of-order
events. Moving, settling, low quality (<0.5), age over one second, or uncertain
translation invalidates assigned-seat confidence. These conservative safety
limits are contract defaults, not newly optimized research thresholds. Fresh
stationary evidence never restores trust automatically. Use **Arrange seats →
Apply / re-anchor here** after checking the physical position. Voice profiles
and anonymous voice memory are retained. Existing Manual tablet moved remains.

An adapter calls `controller.motion_event(event)` through the bounded command
queue; overload is explicit, so a future adapter must stop admitting seat evidence
on delivery failure. The current driver is disabled; snapshots report that fact
and separately label mock/external event provenance. This interface affects
assigned seats; automatic sensor-driven compensation for other spatial modes
remains pending. No relative-yaw angle correction is applied. The linear array
cannot disambiguate mirrored front/back positions; translation/range cannot be
recovered by integrating this IMU into a drift-free room map.

From repository root, PowerShell:

```powershell
& .\.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p test_motion.py -v
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p test_motion.py -v
prototype\Start-Prototype.cmd
```

Tests use synthetic events/temporary people; no mic, sensor or inference.
Outputs: invalid seat state, re-anchor status, bounded latest motion metadata,
and the existing seat-change journal when a session is open. Nothing is enabled
by editing the hardware planning template alone. See
`../docs/CM5_WIRING_AND_BRINGUP.md` and `../docs/HARDWARE_PENDING.json`.
