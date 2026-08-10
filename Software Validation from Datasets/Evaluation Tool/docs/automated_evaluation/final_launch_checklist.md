# Final launch checklist

Do not check a box from expectation; use the produced evidence.

## Repository

- [ ] Both clones are at the final launch commit and branch.
- [ ] Worktrees contain no unexpected source/config changes.
- [ ] Both clones ran `python scripts/materialize_launch_campaign.py --bind-current-commit`.
- [ ] Both generated `worker_assignments/release_binding.json` files are byte-identical, bind both assignments to the final HEAD, and retain the frozen campaign hash.

## Environment and models

- [ ] Both use Python 3.12 `core-cpu`; `pip check` passes.
- [ ] FFmpeg is visible and reports a version on both machines.
- [ ] CUDA is not required by this CPU candidate; no GPU concurrency is enabled.
- [ ] Whisper Base is 145,262,807 bytes and has the frozen SHA-256.
- [ ] Implicit model downloads remain disabled.

## Credentials

- [ ] Campaign confirms `required_credentials: []`.
- [ ] Optional pyannote/Falcon absence is recorded, not hidden.

## Data and RIR

- [ ] Full A preflight reads every assigned source/header/bound.
- [ ] Full B preflight reads every assigned source/header/bound.
- [ ] Native scenarios contain no synthetic noise/RIR.
- [ ] Dining and Restaurant hashes match; Bedroom is excluded; ParkingLot is not substituted.

## Campaign and assignments

- [ ] Campaign hash is `FF833023…66046D4` or the explicitly regenerated final hash.
- [ ] Exactly 41 global scenarios and 25,798 item executions reconcile.
- [ ] A owns 20; B owns 21; intersection is empty; union is all 41.
- [ ] A has at least 7.15 GiB free for run/reserve and 2.15 GiB more before export.
- [ ] B has at least 7.30 GiB free for run/reserve and 2.30 GiB more before export.
- [ ] Component canary passed and the finalist scope was approved.
- [ ] Small gate passed, then standard gate passed.

## Machine A

- [ ] Actual profile is current and full 20-scenario preflight says `READY_TO_LAUNCH`.
- [ ] Real one-item smoke passed.

## Machine B

- [ ] Actual profile is returned; Machine B is no longer `NOT_YET_TESTED`.
- [ ] Full 21-scenario preflight says `READY_TO_LAUNCH`.
- [ ] Real one-item smoke passed; provisional runtime was reviewed.

## Execution, transfer, merge, and analysis

- [ ] One scenario at a time per machine; no unqualified GPU concurrency.
- [ ] Both operators tested status, stop, and assignment-scoped resume.
- [ ] Output locations are writable.
- [ ] Transfer destinations have space and are initially absent.
- [ ] Both export manifests have zero unexported scenarios and validate checksums.
- [ ] Coordinator has at least 15 GiB free and validates both transfers before merge.
- [ ] Merge reports 41/41, no missing/conflicting scenarios.
- [ ] Analysis index/validation/coverage/run/release-status complete.
- [ ] Final report exists at `automated_runs/campaign_05_massive_release/analysis/report/campaign_report.md`.
