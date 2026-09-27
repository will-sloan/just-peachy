# ARM64 native saved-audio attempt: partial, preserved

The supervised A2/A3 QEMU run ended at 2026-09-27 19:25:38 UTC. A2 reached
the unchanged 1,800-second model limit during its second saved-source pass.
The native process received SIGTERM and returned -15 after 1,801.11 seconds.
The controller recorded an empty owned Linux process group. Subsequent exact
Windows PID/creation-time checks found the host, driver and WSL launcher absent.
All eleven admitted source records still match their hashes.

Private audit: `local/n5/native-stream-models-v1-audit-v1/RESULT.json`, SHA256
`21d9256aaedbf1635f9b7e1d39f925edd44d860f184eb811bae90f93a5f32336`.
It binds the host and Linux results, input receipt, stdout/stderr, unchanged
sources and exact closed Windows identities. Original failed output is retained
at `local/n5/native-stream-models-v1`; no transcript is reproduced here.

The native JSONL contains 175 rows. Empty, one-sample and short-tail streams
each report one final and normal stream closure. The full first saved source
completed 715,127 frames, 87 events and five finals with stream closure. The
repeat's last recorded event reached 377,600 frames. Its stream did not finish;
the forced-endpoint case and normal recognizer terminal receipt are absent.

This establishes that the A2 ARM64 artifact loaded its admitted model and ran
the first saved-source pass under QEMU. It does **not** establish the complete
component contract: exact repeated-stream state parity and forced-endpoint
closure remain unverified. The strict reader did not run to an acceptance
result after the timeout. A3 was not attempted. Required models: two; attempted:
one; complete passes: zero; unattempted: one.

The generic recorded error says "Command cancelled or process group not empty".
The underlying receipt disambiguates it: cancellation was `model_timeout`, and
`remaining_group_members` was empty. Do not report a leaked process group or
interpret the completed first stream as a passing full component check.

No unchanged 30-minute retry is scheduled. This result does not accept an N4
profile, validate the ARM64 GUI, prove CM5 speed/RAM fit, or install anything on
the powered-off Pi. `ARM64_FUNCTIONAL_SMOKE` remains false. Baseline Windows
validation and release packaging retain priority within the fixed reserve and
deadline. Any later retry needs a fresh derivative/admission with explicit
scope, exact source/audio bindings and the same complete acceptance contract.
