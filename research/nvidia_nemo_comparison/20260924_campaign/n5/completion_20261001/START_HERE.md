# Just Peachy — start here

**Current release: field-runtime-v29-build-16, one desktop launcher.** Stage,
activation, ten-shortcut archive, independent readbacks and actual normal
idle/Exit passed. Capture stays off until Start and login autostart stays
disabled. The policy-control check started no worker or model; physical
touch, double-click and a new reboot were not tested. v27/v28 remain preserved
rollback references. [Current status](CURRENT_RUNTIME_PROGRESS.md) separates
bounded passes from the failed whole-application hour and unqualified quality.
Read these in order:

1. [MODE_GUIDE.md](MODE_GUIDE.md): operator choices, live/saved sources,
   recording workflow, measurements and experimental limitations.
2. [BACKEND_COMBINATIONS.md](BACKEND_COMBINATIONS.md): diarizer/embedding/profile
   combinations. Sherpa/PnC remain shared; ReDimNet/TitaNet galleries stay separate.
3. [Pipeline architecture and mathematics](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_PIPELINES.md):
   individual pipeline guides and source entry points.
4. [Research adaptations](../extension_20260928/pi_native_20260928/live_runtime_20261003/RESEARCH_ARCHITECTURES.md):
   primary papers, adaptations using existing models, and unreproduced results.
5. [RAM/resource guide](../extension_20260928/pi_native_20260928/live_runtime_20261003/RAM_RESOURCE_GUIDE.md)
   and [native results](../extension_20260928/pi_native_20260928/live_runtime_20261003/NATIVE_RESULTS.md):
   actual2GB observations, CPU/thermal/software limits and possible4GB/8GB benefits.
6. [FIELD_VALIDATION.md](FIELD_VALIDATION.md), [MOTION_GUIDE.md](MOTION_GUIDE.md),
   [INSTALL_HEALTH_AND_RECOVERY.md](INSTALL_HEALTH_AND_RECOVERY.md), and
   [PATHS_AND_BACKUPS.md](PATHS_AND_BACKUPS.md).

The v29 flow is one launcher, choose backend and live/saved source,
Start, Stop/drain, then keep processed, qualified raw+processed, or discard.
Normal live policy is300s; a separate developer path permits one-hour testing.
Persistent recordings are capacity-driven UUID sessions rather than four slots.
Implementation does not establish that every mode sustains real time.

BMI270 retains the microphone-array origin, causal pose timing and device-relative
beam display. Motion suspends unreliable location priors. This six-axis sensor
does not provide reliable absolute room translation or drift-free yaw. Plain
saved WAVs never borrow current tablet motion.

The small ChatGPT handoff is documentation/readable source, not an OS image or
complete model installation. Models, galleries, recordings and transcripts stay
outside the public archive. Older FINAL_*, MOTION_* and DESKTOP_* receipts retain
their original release scope. Historic34-method and incomplete240-cell N4
coverage remain in FINAL_COVERAGE; this runtime update does not complete them.

The single final source handoff and authoritative adjacent readback receipt are named in the [publication guide](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_FINAL_PUBLICATION.md). The guide omits its own ZIP hash to avoid a circular artifact.
