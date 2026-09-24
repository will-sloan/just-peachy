# BMI270: automatic startup reference and three-dimensional rotation

Purpose: use the rigidly mounted SparkFun BMI270 to compensate horizontal
XVF directions during turns and tilt. Existing speech models, C079/C060 spatial
recipes, enrollment, and offline operation remain unchanged. No new model,
internet service, position integration, or dataset sweep is involved.

## Intended installation, described September 22, 2026

**Latest hardware status:** the user clarified that the boards are electrically
connected but NOT yet mounted in the enclosure. `fixed_mount` is therefore
saved as false on the Pi. The worker provides sensor diagnostics; it cannot
modify array bearings or invalidate array locations while loose. Existing
native XVF angles and voice modes continue. After actual assembly, Settings ->
Motion sensor -> **Confirm mounted as described** saves the one-time installation
state and starts the automatic reference. Mark sensor unmounted before taking
the assembly apart again. This installation step is not recurring calibration.

Device coordinates are right-handed, viewed from the FRONT of the upright
portrait display: +X is right, +Y is top, +Z points out of the display toward
the viewer. Sensor +X points down, +Y points right, +Z points forward. Looking
at the back reverses apparent left/right; a circle with a cross means into
the surface being viewed. MIC3 is at the right end, the native XVF 0-degree end.
These are user-reported INTENDED directions, not measured physical alignment.

The raw Bosch sensor-to-device transform is:

```text
v_device = R_DS v_sensor
R_DS = [ 0  1  0 ]      x_device =  y_sensor
       [-1  0  0 ]      y_device = -x_sensor
       [ 0  0  1 ]      z_device =  z_sensor
```

This matrix has determinant +1. It maps acceleration and angular velocity with
the same signs. The array axis toward native 0 degrees is device (+1,0,0).
The approximate sensor position measured FROM the microphone center is
(-0.07,-0.09,-0.05) metres: left, down, behind. The vector FROM the sensor TO
the array center is therefore r=(+0.07,+0.09,+0.05) metres. These dimensions are
editable in the external configuration; improving them does not change gyro
rotation or require recurring manual calibration.

Every rigidly mounted point shares angular velocity and orientation. Offsets
do not multiply or divide the rotation angle. For acceleration at array center:

```text
f_center = f_sensor + (alpha x r + omega x (omega x r)) / 9.80665
```

Here f is specific force in g, omega is radians/second, alpha is radians/second
squared, and all vectors use device axes. Gravity cancels in this difference.
The first term is tangential acceleration, the second centripetal acceleration.
The angular-acceleration derivative has a 0.1-second low-pass time constant to
limit noise. The result supports gravity-feedback/movement checks. It is NOT
integrated twice to claim room position. Array translation and talker ranges
remain unknown.

## Attitude, horizontal angles, and startup

`inertial_geometry.py` holds vector, rotation and lever-arm math. `imu.py` uses
a normalized Hamilton quaternion (scalar first) mapping current device axes
to the initial device orientation. It integrates all three corrected gyro
components, not a projection onto a permanently fixed initial gravity axis.
Quiet accelerometer data supplies complementary gravity feedback (0.6/s).
Dynamic acceleration suppresses this feedback rather than being mistaken for tilt.

At every app start, two quiet seconds estimate gravity and gyro bias and create
a new reference. No heading is loaded from the previous boot. Small bias
changes are adapted slowly during detected stillness (60-second time constant).
Automatic stillness detection cannot distinguish arbitrarily slow constant
yaw from gyro bias; booting/resting without movement is an assumption, not a
proof. There is no user calibration wizard or need to reset after ordinary tilt.

The startup horizontal X reference is the projection of the native 0-degree
array axis onto the gravity-horizontal plane. Horizontal Y is up cross X.
Positive turn is counterclockwise viewed from ABOVE the device; clockwise is
negative. At upright portrait, positive yaw is about device +Y, which is sensor
-X with this mounting. When lying screen-up, it is about device +Z/sensor +Z.
A lift around the left-to-right microphone baseline changes tilt, not this
horizontal bearing. Compound rotations use the full quaternion.

For current unit array axis a in the startup frame and assumed horizontal
talker bearing theta, the linear array supplies this projection:

```text
a_x cos(theta) + a_y sin(theta) = cos(native_XVF_angle)
theta = atan2(a_y,a_x) +/- acos(cos(native_angle)/hypot(a_x,a_y))
```

This handles a tilted baseline; simply adding yaw would not. It assumes talker
direction is horizontal (approximately microphone height). Source elevation
cannot be recovered uniquely from a linear array. With a horizontal baseline,
rotation about that baseline does not alter the projection, even for an elevated
source. When the baseline is nearly vertical (horizontal projection <0.25),
azimuth is ill-conditioned and support is suspended until geometry improves.

Both mirrored solutions are evaluated. The retained 0-180-degree tracker can
use a cue only if exactly one falls in the initial 5-175-degree half-plane.
This is an explicit half-plane assumption, not proof of which side a person is
on. Rear/front ambiguity, inconsistent elevation, and endpoints never get
clamped into a made-up direction. Raw native angles remain in Beam diagnostics.

## Continuity and honest limits

Normal tilt, multiple revolutions, and more than 30 seconds of turning do not
erase the reference. The previous 60-degree/30-second limits are removed.
Acceleration pauses cue trust briefly, clears old locations (including tracker
location memory), and retains orientation. Fresh voice/direction evidence can
rebuild locations automatically once motion settles; identities are not erased.
Assigned seat assumptions still require Apply after actual relocation. Rotating
without translation preserves them when the inertial evidence remains usable.

Missing >150ms of samples or clipping cannot recover unobserved rotation. The
software invalidates old locations, automatically acquires a NEW frame after
two quiet seconds, and reports the frame generation and last reference-loss
reason. I2C read failures retry with 2..30-second backoff under the same exclusive
lease. There is no false claim that an interruption preserved room heading.
Stale data is never shown as fresh. Causal timestamp and frame/generation checks
exclude future samples and old-frame cues, even if a queued callback is late.
Tracker changes execute on its dispatcher, not the sensor or audio thread.

BMI270 has no magnetometer or other absolute heading reference. Gravity corrects
tilt, NOT yaw. Unlimited drift-free direction, recovery of motion during power
loss, and exact compensation for translations are physically unavailable here.
A deliberately labeled engineering drift allowance reduces spatial weighting:
2 + 0.002 * elapsed_seconds + 0.002 * total_rotation_degrees, with multiplier
exp(-allowance/10). This is neither measured accuracy nor a confidence interval.
It grows with time even at rest. Existing tracker reliability gates still apply.
An external heading/position reference would be needed for stronger guarantees;
even a magnetometer alone would not determine speaker positions or translations.

## Inputs, outputs, and configuration

Inputs: BMI270 at I2C1 address0x68, chip ID0x24; 50Hz acceleration +/-4g and gyro
+/-500 degrees/second; host monotonic receipt times; explicit fixed geometry;
existing XVF native beam angles. One bounded worker and ctypes library owner,
256 pose-history entries, 100 startup samples. The host polls at up to 100Hz to
read the 50Hz data-ready samples despite I2C overhead. Receipt time is not a
hardware-synchronised acoustic/IMU timestamp; fast movement accuracy still
needs qualification. No extra inference.

External Pi `~/JustPeachy/data/imu_config.json`:

```json
{
  "library": "/home/peachyprototype/JustPeachy/tools/bmi270/libpeachy_bmi270.so",
  "lease_path": "/home/peachyprototype/JustPeachy/data/imu.lock",
  "bus": "/dev/i2c-1", "address": 104,
  "fixed_mount": false, "rotation_compensation": true,
  "mount": {
    "sensor_to_device": [[0,1,0],[-1,0,0],[0,0,1]],
    "array_zero_axis_device": [1,0,0], "axes_verified": true,
    "sensor_position_from_array_m": [-0.07,-0.09,-0.05],
    "offset_verified": true
  }
}
```

`axes_verified` means the intended axes were explicitly supplied/confirmed;
it does not claim completed assembly or physical accuracy testing. `offset_verified` means the signed
directions were confirmed, not that approximate dimensions are survey-grade.
Do not copy this installation's orientation to differently mounted hardware.
Missing/unverified axes never produce a trusted corrected cue. Windows or file
sessions without `imu_config.json` open no IMU. Ordinary live microphone and
enrollment/profile behavior are preserved.

Outputs: relative turn, quaternion, freshness, sensor/array specific forces,
reference generation, last interruption, estimated cue weight, bounded counters.
These contain no audio, transcripts, or personal profiles. Settings -> Motion
sensor shows status and optional rotation assistance. Starting a new reference
manually remains available, but is not required after an ordinary lift/turn.

## Run and test

From the repository root, PowerShell:

```powershell
$env:PYTHONPATH="$PWD;$PWD\prototype;$PWD\prototype\vendor;$PWD\prototype\tests"
& .\.edge-speech-env\python.exe -m unittest test_imu test_motion test_live_spatial test_seats test_ui -q
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
set PYTHONPATH=%CD%;%CD%\prototype;%CD%\prototype\vendor;%CD%\prototype\tests
".edge-speech-env\python.exe" -m unittest test_imu test_motion test_live_spatial test_seats test_ui -q
prototype\Start-Prototype.cmd
```

On the installed Pi, normal startup is automatic and offline. To launch manually
with no other GUI instance running, from its desktop terminal:

```bash
python3 ~/JustPeachy/install/releases/proto1-cm5-20260922-rc2/release_tools/launch_current.py \
  --root ~/JustPeachy/install --data-root ~/JustPeachy/data -- --fullscreen
```

The retained launcher selects the activated current release; its own directory
name does not select the application version. Native build commands and licence
are in `../native/bmi270/README.md`. Bounded real capture tests and their inputs/
outputs are documented in `../tools/README_CM5_CHECKS.md`. Synthetic matrix-ground-
truth tests establish math/contracts, not measured hardware turn accuracy.

Sources: [SparkFun hardware guide](https://docs.sparkfun.com/SparkFun_Qwiic_6DoF_BMI270/hardware_overview/),
[Bosch datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi270-ds000.pdf),
[quaternion complementary-filter equations](https://ahrs.readthedocs.io/en/latest/filters/mahony.html),
[inertial navigation error overview](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-696.html).
