# Fill-in hardware profile

Use HARDWARE_PROFILE.json as a planning template. It remains disabled; every
GPIO, bus, address, interrupt and display-controller assignment is null. It is
not a device-discovery result. Target is CM5 2GB total RAM, 32GB eMMC, no wireless.

Initial XVF path is USB UA audio/control. Record actual firmware/readback and
matching host command-map ABI before activation. Older bundled Raspberry Pi host
tools are ARM32 and are excluded from the new ARM64 runtime. A matched ARM64
XMOS host/control-map build is still pending; source preparation is not a build.
See XMOS_BUILD_BLOCKER.md for the exact local license/entitlement gate.
No firmware is changed. Do not infer pins from older bring-up documentation.

Record carrier/extender revisions, power/ground, physical pin versus BCM number,
pin mux/conflicts, bus/address, IRQ polarity, pull/debounce, actual display driver
and touch transform. Validate actual wiring before enabling any driver.

Camera is optional/on-demand, not continuous. BMI270 requires explicit sensor
axes → tablet rotation and sensor → host-monotonic clock mapping, with uncertainty.
Initially it may report stationary/moving/settling and require manual re-anchor.
It cannot establish drift-free position or absolute yaw. Linear-array front/rear
ambiguity persists. Manual/assumed labels retain that provenance and are never
self-certified identity evidence.
