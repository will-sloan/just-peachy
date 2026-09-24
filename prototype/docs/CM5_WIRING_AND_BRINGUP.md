# CM5 wiring worksheet and arrival checklist

**Actual 2026-09-22 installation supersedes this planning worksheet:** see
[CM5_INSTALL_20260922.md](CM5_INSTALL_20260922.md) and
[CM5_I2S_MIGRATION.md](CM5_I2S_MIGRATION.md). The current hardware uses the
onboard linear microphones via 40-pin I2S/I2C, the working Freenove DSI screen,
and a verified BMI270 at I2C1 0x68. Live motion behavior is documented in
[README_IMU.md](../app/README_IMU.md); the original sensor-free statements below
describe the earlier task08 release.

Status: **software-prepared; hardware-pending**. Use the common Windows/Linux
source. Target: CM5 2 GB total RAM, 32 GB eMMC, no wireless, CM5IO SC1967 with
ED-PI400EXT-R extender and a 480×800 portrait touch display. The hardware model
names are the supplied plan, not a discovery result. Fill a local copy of
`HARDWARE_PENDING.json`; unknowns remain null and optional drivers disabled.

| Connection | Intended role | Fill and verify before enabling |
|---|---|---|
| CM5 → CM5IO | Compute and eMMC | Module/carrier revision, connector seating, mounting, cooling and actual power budget |
| Wired Ethernet | SSH/SCP application updates | Host/user, verified SSH host key, address, non-root access; no wireless dependency |
| USB → XVF3800 | Initial UA audio + USB control, built-in linear microphones | USB identity, exact firmware/array/rate readback, host binary + command-map hashes, capture endpoint and permissions |
| Display/touch | Portrait UI and primary input | Exact panel/controller/driver, HDMI vs DSI/other interface, connector/cable orientation, touch bus/address, framebuffer rotation and touch transform |
| Extender | Board interconnect | Schematic revision, routed/reserved nets, physical pin numbers AND GPIO names/lines; never presume exposed pins are free |
| BMI270 breakout | Optional movement evidence | I2C or SPI, bus/controller, address/chip select, rail/logic level, physical pins, GPIO lines, interrupt, axes, rate and clock mapping |
| Camera | Optional on-demand profile photo | CSI port, cable contacts/pitch/type, driver, focus driver/control and permission; no continuous capture |
| Optional buttons | Logical up/down/left/right/select/back | Verified unused pin/line, active level, pulls and debounce; touch-only operation is sufficient |

Pin worksheet (create one row for every signal): component signal → connector
and **physical header pin** → **BCM GPIO / gpiochip line** → alternate function →
extender net → rail/level → direction/pull → owner/driver → conflict check →
verified by/date. Physical header and BCM numbering are separate fields; no
numerical assignments are supplied. Check I2C/SPI/interrupt/display conflicts,
CSI/DSI connector sharing, reset/boot straps, backlight/current demand, common
ground and possible back-power paths before applying power. Confirm connector
pin 1 and ribbon contact orientation from the exact board and panel drawings.

CM5IO's official power guidance distinguishes supply ratings and peripheral
budgets; inspect the actual supply and full assembly rather than assuming the
extender powers everything. eMMC imaging/rpiboot and XVF firmware flashing are
separate provisioning operations, outside routine app deployment. Neither ran
in task08. [Raspberry Pi Compute Module documentation](https://www.raspberrypi.com/documentation/computers/compute-module.html).

BMI270 supplies accelerometer/gyroscope measurements; it is not an absolute
room-position or drift-free yaw sensor. Calibration, axis alignment, timestamps
and stationary detection require physical validation. The current software only
accepts timestamped mock/external motion events and invalidates seat trust.
Future relative rotation compensation must retain the linear array's mirrored
ambiguity; uncertain translation/range requires re-anchoring. [Bosch BMI270](https://www.bosch-sensortec.com/en/products/motion-sensors/imus/bmi270/),
[Cambridge inertial-navigation error study](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-696.html).

## When hardware arrives

1. Verify module, carrier, extender, supply, panel and cable part numbers. Complete
   the worksheet and null fields; do not turn on sensors based on a template.
2. Provision a CM5-compatible 64-bit OS separately. The prepared wheel target is
   Bookworm/aarch64, CPython 3.11, glibc ≥2.36. Record `uname -m`, OS/Python and
   `ldd --version`; a different Python target needs a new corresponding lock.
3. Establish wired networking and non-root SSH with host-key verification. Use
   the staged application workflow, not disk imaging for each code change.
   [Official remote access and file transfer](https://www.raspberrypi.com/documentation/computers/remote-access.html).
4. Transfer source archive, receipt, existing pinned wheels, and shared models
   once. Install documented OS libraries separately. Validate hashes/imports,
   headless saved-file inference, activation, then idle GUI with mic Off.
5. Verify 480×800 physical rendering, rotation and touch calibration. Test every
   edge, scrolling and keyboard input. Missing touch/camera/IMU is not a headless
   replay blocker. Optional GPIO must map to logical input, not own capture.
6. Build/qualify firmware-matched native ARM64 XVF host control. The supplied
   v3.0.0 `rpi` binaries from firmware v3.2.1 are ARM32. Keep USB driver and command
   map beside the host helper; run `file`, `readelf -h`, `ldd`, `--help`, then
   read-only version/route queries. Record hashes before live use. See the exact
   vendor-source build notes in `PI_DEPLOYMENT_WORKFLOW.md`. No DFU/flash step is
   part of app install. Verify ordinary live UA routing rather than packed tests.
7. Select the actual XVF capture endpoint and configure control explicitly. Start
   with captions only, then enrollment with a consenting person, Stop/drain,
   restart, modes, save/reopen, and spatial freshness/movement checks. No default
   PC microphone fallback or output-device changes are permitted.
8. Measure the **whole 2 GB system**: available RAM/swap/OOM, process RSS, CPU,
   latency/queue growth, thermals/throttling and eMMC free space/write load under
   a representative session. Windows measurements do not qualify these limits.
   Verify audio retention quotas and disk-full behavior before extended use.
9. With the app stopped, exercise compatible update and rollback while hashing
   private profiles beforehand/afterwards. Never downgrade paragraph profiles
   with a pre-task06 reader. Use the current updater's feature compatibility check.
10. Only then enable one verified optional peripheral at a time. Check IMU
    timestamps/axes/quality and manual re-anchor; camera capture/focus on demand;
    button debounce/mux conflicts. Record pass/fail/remaining issues per device.

Platform boundaries remain: `live_audio`/`beam_control` own audio/control;
Tk UI owns display/touch; `paths`/`people`/`sessions` own external storage;
`motion` owns event safety; disabled `hardware_adapters` reserve camera/GPIO.
There is no claim of working native peripheral drivers or CM5 timing yet.
