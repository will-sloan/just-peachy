# Mounted motion: operation, geometry and limits

The mounted BMI270 integration is deployed in **field-runtime-v27**. All ten
existing backend profiles share the same motion-enabled frontend and source
adapter. Sherpa ASR, Pyannote/Nemotron diarizers and ReDimNet/TitaNet weights are
unchanged. Three of four recording slots remain after the integration recording.
The manager is idle, capture off, display270. The current ten profile shortcuts
and rollback are on the desktop; older generated icons were backed up and archived.

## Normal use

Open a profile, choose New recording, and use the existing consent/Start/Stop/
Save/Return controls. The sensor starts with the frontend. Its fixed mounting
configuration is already saved; it automatically learns a relative reference
after roughly two quiet seconds. No manual zero is required. If startup load or
a sensor interruption creates a gap, location trust is suspended and a new
reference is acquired automatically. Voice processing does not acquire a second
sensor or a separate sensor per speaker/backend.

Settings → **Orientation graphic · show / hide** toggles the small upper-right
tablet/arrow diagnostic. It is hidden by default. Tap it to make the current
heading point upward **in that graphic only**; this does not alter identity,
seat or audio coordinates. The graphic updates at most10Hz while visible, using
the existing GUI poll. Opening a shortcut never starts microphone capture.

| Routes | Motion behavior |
|---|---|
| baseline, baseline-titanet, baseline-anonymous | Shared live pose and microphone-frame beam display; existing spatial/seat consumers receive motion-aware cues where enabled |
| d1-delayed, d1-delayed-titanet, d1-anonymous | Same shared live motion/source path; voice-only/native anonymous modes retain their existing identity rules |
| d1-streaming-saved, d1-streaming-titanet-saved, d1-chunk52-saved, d1-chunk52-titanet-saved | Live sensor may drive diagnostics, but current tablet motion never changes recorded WAV directions |

This does not inject angles into neural embedding vectors or rewrite Nemotron's
internal diarizer. Existing position-based association uses corrected cues;
voice-only modes do not gain an invented position rule. Plain WAVs have no
recorded pose/range metadata. Replay of a synchronized motion sidecar is not
implemented. The original120s microphone/Chunk52 and30s saved Streaming limits,
model galleries and optional raw/processed recording controls remain.

## Coordinate model

Device axes are +X right, +Y toward the top, +Z out of the screen. The confirmed
sensor axes are +X down, +Y right, +Z out. The sensor-to-device rotation is
`[[0,1,0],[-1,0,0],[0,0,1]]`.

Live XVF readback reported a linear array (type1), with positions in metres:
MIC0=(-.04995,0,0), MIC1=(-.01665,0,0), MIC2=(.01665,0,0),
MIC3=(.04995,0,0). Its geometric center is(0,0,0). The user's approximate
measurements therefore place the IMU at(-.045,-.160,-.015)m relative to the
array center. The difference between the rounded10cm measurement and9.99cm
firmware span is below the precision of the supplied mount measurements.

The worker integrates gyro angular velocity into a quaternion, with gravity
correction during quiet periods and gradual quiet gyro-bias adaptation. For the
offset sensor, the center-specific force uses the rigid-body correction
`f_center = f_sensor + alpha × r + omega × (omega × r)`, where `r` runs from
the IMU to the microphone-array center. This helps distinguish rotation-induced
acceleration at the off-center sensor from translation.

Raw beam arrows remain **relative to the actual microphone array**. Location
association transforms a time-matched bearing into the current relative anchor
frame; labels are projected back onto the current device axis for display.
Audio callbacks receive bounded, timestamped beam records from the existing
serialized control worker. No hardware access or disk write is added inside the
audio callback. Future pose samples are never applied to earlier audio.

The [XMOS XVF3800 guide](https://www.xmos.com/documentation/XM-014888-PC/pdf/xvf3800_user_guide_v3.2.1.pdf)
defines the array/beam controls. The [SparkFun BMI270 hardware guide](https://docs.sparkfun.com/SparkFun_Qwiic_6DoF_BMI270/hardware_overview/)
describes the six-axis accelerometer/gyroscope board. Live geometry readback is
retained in the integration receipt, rather than inferred solely from a diagram.

## What cannot be inferred

There is no magnetometer or external position/range reference. Relative yaw can
drift; a linear microphone array also retains front/back ambiguity. Integrating
accelerometer noise twice cannot provide reliable room position. Detected
translation therefore clears/suspends location assumptions while preserving
voice identity evidence; it does not claim a stationary speaker's room position.
Smooth constant-velocity translation after acceleration can be unobservable.
The stationary/moving indicator is a sensor-based estimate, not perfect truth.
Turning the tablet cannot make an acoustically ambiguous source uniquely located.

## Performance and actual evidence

The worker uses one native sensor handle, one sleeping thread,50Hz samples and
100Hz data-ready polling. Quaternion/vector operations are small fixed-size
calculations. Histories/beam queues are bounded; the graphic is inactive when
hidden. Beam getters reuse the existing serialized worker, approximately five
groups/second, without per-backend polling threads.

On the actual CM5 during the new5.25s recording, the IMU thread used
**0.06231CPU-seconds over5.15037seconds:1.21% of one core**, delivering50.29samples/s.
This measures the IMU thread, not beam-getter subprocess CPU or battery energy.
An earlier8.03s idle whole-frontend observation used0.64CPU-seconds (~8% of one
core), including GUI and all frontend threads. No battery-endurance claim follows.

The successful recording contains84000processed samples,525audio blocks,
79causally ordered beam records, no beam queue drops and44pose records. Eight
early pose records explicitly withheld spatial trust after a startup sensor
gap; the remaining36 were valid after automatic stationary recovery. Stop/Save/
Return, source/model/archive/command closure, local backup and two independent
complete PC copies passed (each201files,3641161bytes,27directories). Firmware
geometry getters succeeded while the same audio loop was active.

The earlier physical turn produced approximately-88.9° for the requested
clockwise90° turn and returned to about+1.0°. It is a basic functional check,
not calibrated heading accuracy. The debug graphic show/tap/hide passed on the
identical final common capsule. All ten profile pins were verified; unchanged
model routes were not exhaustively rerun. No noisy-human recognition improvement,
long-term drift, physical touch or battery endurance was established here.

## Files, recovery and validation

Current Pi root:
`/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v27`.
Mount config: `/home/peachyprototype/JustPeachy/data/imu_config.json`.
PC code and run instructions: `Resumes/imu_integration_20261002/README.md`.
Private evidence: `local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002`.
The detailed review is `delivery-review-v1/RESULT.json`; audio remains private.

Use the new `renew_motion_runtime.py --plan` and documented renewal command
when a finite batch is exhausted. The older Refresh-JustPeachy reconstructs the
historical capsule and would omit the new integration. The prepared renewal
wrapper retains the motion capsule; its component operations have execution
evidence, while the combined wrapper was only compiled/planned.

Runtime25's graphic failure and26's microphone-firmware startup fault remain
preserved. The one conditional XVF recovery was tied to the actual active-loop
AEC255 failure, followed by matching version/build readback and the successful
runtime27 recording. Do not schedule periodic resets. Old volatile state was
unreadable and is not claimed restored. Rollback restores the prior application;
it is a recovery path, not the new motion-qualified frontend.

For real-world validation: first observe the native beam view with a stationary
speaker, then turn the tablet; next translate it and confirm location trust is
cleared without forcing a voice-identity change. Compare ReDimNet/TitaNet using
the same consented recordings. Include tilt, a short sensor interruption, noisy
overlap and longer stationary drift observations. Do not interpret Unknown from
an empty TitaNet gallery as a motion failure. Record observations using the
existing FIELD_RUN_TEMPLATE and keep raw/processed clocks and motion traces.
