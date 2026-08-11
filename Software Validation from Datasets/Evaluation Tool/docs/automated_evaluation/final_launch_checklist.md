# Final CPU/CUDA launch checklist

Check every item. Any unchecked blocking item means do not launch the massive campaign.

## Repository and contracts

- [ ] Both machines are on branch `handoff` at the same approved final commit.
- [ ] `git status --short` is clean before runtime artifacts.
- [ ] One mode is selected on both workers: CPU campaign `campaign_05_massive_release` or CUDA campaign `campaign_06_massive_release_cuda`.
- [ ] Selected campaign and scenario catalog hashes match the launch control sheet.
- [ ] Runtime `release_binding.json` names the checked-out commit on both machines.
- [ ] Assignment validation reports 20 A scenarios, 21 B scenarios, zero overlap, and 41 total.
- [ ] Preserved CPU campaign files and identities are unchanged.

## Environment and assets

- [ ] CPU workers use `.venv`, `core-cpu`, `cpu`, float32, CPU PyTorch, and require no GPU.
- [ ] CUDA workers use `.stage8-envs/core-cuda`, `core-cuda`, `cuda:0`, float32, CUDA PyTorch, and nonzero VRAM.
- [ ] Both modes pass `pip check`, verifier, real evaluator smoke, and no-fallback checks.
- [ ] Whisper Base is 145,262,807 bytes with SHA `ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E`.
- [ ] FFmpeg is visible in the launch shell.
- [ ] Every licensed source file and segment bound is readable.
- [ ] Dining and Restaurant RIR hashes pass; Bedroom remains excluded without substitution.
- [ ] A has at least 7.2 GiB and B at least 7.3 GiB free; coordinator has at least 15 GiB.
- [ ] No campaign credentials are required or present in shared artifacts.

## Readiness and scientific authorization

- [ ] Machine A complete preflight says `READY_TO_LAUNCH`, 20/20 scenarios, 12,368 items.
- [ ] Machine B complete preflight says `READY_TO_LAUNCH`, 21/21 scenarios, 13,430 items.
- [ ] Machine B runtime estimate was measured on its own hardware.
- [ ] Component canary is approved for the exact selected CPU or CUDA configuration.
- [ ] Small gate is approved.
- [ ] Standard gate is approved and prerequisite evidence is frozen.
- [ ] For CUDA, both operators close unrelated GPU-heavy applications and record launch time; CPU operators record a quiescent system.
- [ ] For CUDA, one GPU-heavy scenario at a time is configured on each machine.

## Execution and completion

- [ ] Both matching wrappers pass `-PreflightOnly` before launch.
- [ ] CPU uses unsuffixed launch wrappers; CUDA uses `_gpu` launch wrappers.
- [ ] Operators know the status, controlled stop, and `-ResumeStopped` commands.
- [ ] Each assignment completes with checksum-valid artifacts and no unexplained missing/failed items.
- [ ] Each worker exports its own transfer folder; transfer checksums validate.
- [ ] Merge reports 41/41 global scenarios, no missing work, and no conflicting duplicate.
- [ ] Analysis receives the approved standard-gate evidence.
- [ ] Final report exists at `automated_runs/campaign_05_massive_release/analysis/report/campaign_report.md` for CPU or `automated_runs/campaign_06_massive_release_cuda/analysis/report/campaign_report.md` for CUDA.

## Sign-off

- [ ] Amir approves Machine A evidence.
- [ ] Machine B operator approves Machine B evidence.
- [ ] Scientific owner authorizes the massive run.
- [ ] Final verdict has been changed from `NOT_AUTHORIZED_FOR_MASSIVE_LAUNCH` only after all blocking boxes above are checked.
