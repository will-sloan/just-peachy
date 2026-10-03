# Just Peachy: start here

> Current October3 update: **v28, desktop-first startup**. Use the ten desktop
> shortcuts; choose **Exit to desktop** in the main manager to close normally.
> Four recording slots remain. See [DESKTOP_GUIDE.md](DESKTOP_GUIDE.md) and
> DESKTOP_RELEASE_INDEX.json. Earlier v27 measurements below remain historical.

**The prepared CM5 has field-runtime-v28 installed with mounted BMI270 integration.**
It is left at the desktop, capture off, display 270, with **four recording slots remaining**
and ten backend shortcuts plus rollback. No recording starts by opening a profile.

Read [MODE_GUIDE.md](MODE_GUIDE.md) for the ten diarizer/embedding combinations,
recording controls and PC commands. Read [MOTION_GUIDE.md](MOTION_GUIDE.md) for
automatic calibration, array-centered geometry, the optional orientation graphic,
and what the six-axis sensor can and cannot infer. Sherpa ASR, ReDimNet/TitaNet
and the existing Pyannote/Nemotron choices are retained.

The retained v27 shared integration passed one native 5.25-second processed recording,
normal Stop/Save/Return/closure, local backup and two complete independent PC
copies. It measured about 1.21% of one core for the IMU thread at 50.29 samples/s.
All ten profiles bind the same code; the unchanged model combinations were not
all rerun. Earlier all-profile and raw-recording evidence remains separately scoped.

The sensor handles relative rotation and tilt, with the microphone-array center
as origin. Detected translation suspends location assumptions; reliable absolute
room position is unavailable. Relative yaw can drift. Live beam arrows stay
device-relative, and plain saved WAVs never borrow current tablet motion.

[INSTALL_HEALTH_AND_RECOVERY.md](INSTALL_HEALTH_AND_RECOVERY.md) and
[PATHS_AND_BACKUPS.md](PATHS_AND_BACKUPS.md) cover renewal, rollback and storage.
Follow DESKTOP_GUIDE for renewal limitations; older renewal wrappers do not preserve this desktop-first change. The 91,554,957-byte v23 kit omits motion. The current code is installed
and independently backed up. The new small handoff includes guides and readable
motion source, not models, recordings or a standalone OS image.

Current receipts: MOTION_RELEASE_INDEX.json, MOTION_CHECKLIST.json and
MOTION_HANDOFF_RECEIPT.json. Older FINAL_* receipts remain immutable v23 history.
Physical touch, cable-disconnected coldboot, battery endurance, long-term drift
and noisy-world recognition remain real-world validation, not completed claims.
Use FIELD_VALIDATION.md/FIELD_RUN_TEMPLATE.json. FINAL_COVERAGE retains the
N1-N5/34-method denominator and incomplete full 240-cell N4 comparison.

The approved motion source is remotely backed up at commit
`ed27d04b6131106c400bda828a64d00274095c56`; see MOTION_REMOTE.json.
Use the current MOTION_HANDOFF_RECEIPT.json for the latest verified archive.
The previous upload approval hold is resolved. No new native test was needed
for this documentation refresh; hardware observations remain the recorded v27 check.
