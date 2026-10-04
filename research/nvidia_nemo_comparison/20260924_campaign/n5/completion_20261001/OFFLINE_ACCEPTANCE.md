# Offline validation and physical checks

The v29 runtime uses local pinned model assets and local motion/audio interfaces;
no first-run download or network service is required by its pipeline. The final
release status, asset inventory and activation evidence are identified in
CURRENT_RUNTIME_PROGRESS and the final v29 release index.

Earlier candidate16/22 software socket-denial tests and v27 motion checks are
historical evidence for those releases. They are not a fresh network-isolation,
coldboot or physical-touch test of v29. Local-asset hash verification does not
by itself establish cable-disconnected startup.

Before field use, with the final release and recoverable backups available:

1. Confirm desktop-first startup, display270 and capture off. Open the one
   launcher manually and inspect the selected backend/source.
2. Check physical touch, Start, Stop/drain and post-Stop keep/discard controls.
3. After closing capture and preserving data, perform a cable-disconnected
   startup check with the documented local rollback available.
4. Record within the300s normal policy and storage admission; reopen the saved
   processed timeline. A developer hour is a separate explicit test.
5. Reconnect only as needed for verified PC copies. Keep source/tap/clock metadata
   and the original recording until the copy is independently read back.

Record actual observations in FIELD_RUN_TEMPLATE. Do not convert a software
network restriction or an SSH disconnect into proof of physical unplugging.
Noisy-human WER/DER, named-speaker improvement, battery endurance and power-cut
durability require their own observations.

BMI270 fusion and array-centered rotation are local. Relative yaw can drift;
reliable absolute room translation is unavailable. Motion/gaps suspend spatial
trust, and current tablet pose must never be applied retrospectively to a plain
saved WAV. See MOTION_GUIDE and the per-pipeline documents.
