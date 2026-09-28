# Pre-Pi development status

The new user-authorized window is active through checkpoint 2026-09-28
22:20:48 UTC. Original campaign closure and acceptance scopes are unchanged.

- Original Controller reproduced the immediate late-worker Close rejection
  using a delayed thread and failed-finalization fixture, without models or
  devices. Evidence: local/n5/prepi-20260928/shutdown-tests-v1/parent-reproduction.txt.
- Fresh private source local/releases/prepi-shutdown-v1 adds a five-second
  total cleanup join with named remaining workers. The 60-second inference
  drain and failed-session outcome are unchanged.
- Four new regressions and ten existing lifecycle tests passed. Four new
  storage-budget boundary tests also passed. These are model-free checks.
- First actual-audio preflight refused existing virtual-environment links;
  no worker started. Its failed code/evidence remains preserved. The corrected
  resource census matches the six links in the prior verified census and
  refuses new links in window outputs.
- A0/D1/E0 a0-d1-e0-v2 and A2/D1/E0 a2-d1-e0-v1 both independently passed
  the actual one-file Windows render/save/reopen/delete protocol. All 715,127
  source samples reached ASR and D1; E0 was loaded and called 20 times.
- A0 a0-restart-v1 and A2 a2-restart-v1 independently passed two complete
  EOF/Stop/Start cycles with one ASR load, one E0 load and two streams each.
  The two cycles had identical speaker activity and stored text/source timestamps.
  All application/coordinator/supervisor owners exited normally. These are two
  repetitions of the same 44.695-second saved synthetic source, not endurance,
  early cancellation, a full bank or independent real-world validation.
- New Windows launchers passed read-only binding checks for both combinations;
  the agent did not launch them visibly. See README_PREVIEW.md.
- G01/G02/G03 shadow observer: six model-free safety tests passed. A2
  a2-shadow-v1 and A0 a0-shadow-v1 both independently passed actual Windows
  one-file shadow tests. Full PCM/sample counts, captions/source timestamps,
  native speaker activity and save/reopen/delete matched their ungated controls.
  Actual skipped samples: zero. Observer cost was 0.248s A2 / 0.229s A0 over
  44.695s of source, excluding later JSON serialization. This file is 65.90%
  exact digital zero. Proposed skipped fractions (with 300ms guards) were
  60.89% exact-zero, 71.72% -55dBFS and 79.42% -45dBFS. These are conditional
  proposals on one sparse synthetic clip, not speech accuracy or achieved speed.
- A remaining portability issue was identified: the E0 runtime loader still
  validates a retired TitaNet manifest unconditionally. A fresh derivative must
  restrict that dependency to E1 without weakening D1/runtime hash checks.
  Fresh source local/n5/prepi-20260928/derivatives/e0-runtime-v1 implements that
  repair; six dependency-isolation tests passed. Actual A2 a2-e0-runtime-v1 and
  A0 a0-e0-runtime-v1 independently passed with E1 fields removed. Both retained
  exact parent PCM/sample, activity and caption/source-timestamp parity, E0 use,
  full lifecycle and normal owner closure. See README_E0_RUNTIME.md and
  README_E0_RUN.md. The two-cycle restart evidence above belongs to the earlier
  shutdown derivative; early-stop/new-derivative restart remains a separate gate.
- CHECK_SUMMARY_V1.json binds all eight narrow Windows run reviews and three
  preserved model-free regression logs. All eight run owners have exited.
  The current saved-file launchers bind the E0-only derivative; both read-only
  launch checks pass. START_HERE_PREPI.md gives the two named launch commands.
  The six-hour scheduled follow-up remains active and follows NEXT.md.

Run and independent-review instructions: README_RESTART.md,
README_RESTART_REVIEW.md, README_SHADOW_RUN.md and README_SHADOW_REVIEW.md.
Private review receipts are in local/n5/prepi-20260928/*-REVIEW.json. Source
bound to any run must remain unchanged. New data and model weights stay private.

Pending: broader restart/controls/resource coverage, full N4 panel and full ARM64 stack.
No optimized real-time performance, Pi readiness, native hardware result or
new stage acceptance is claimed. The scheduled follow-up was reactivated with
the new window limit and all saved-audio, privacy and resource restrictions.
