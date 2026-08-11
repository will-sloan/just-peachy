# Final launch checklist

## Production completion

- [x] CPU setup is automatic, isolated, idempotent, and verified from a clean clone.
- [x] CUDA setup is automatic, isolated, idempotent, and verified from a clean clone.
- [x] Whisper Tiny, Base, Small, SpeechBrain ECAPA, and Silero are installed by setup; configured model hashes validate.
- [x] FFmpeg is installed or detected automatically and wrappers refresh PATH without a terminal restart.
- [x] No production API key, credential, license acceptance, or hosted account is required.
- [x] Authorized Machine A datasets are discovered/linked automatically without copying raw audio.
- [x] CPU real evaluator smoke produces one valid prediction, metrics, plots, and report.
- [x] CUDA real evaluator smoke uses `cuda:0` on the RTX 3080 and records nonzero VRAM.
- [x] CPU and CUDA float32 are distinct canonical scientific identities; CUDA cannot silently fall back.
- [x] The 7-scenario executable canary and all 9 active component qualifications pass.
- [x] The 26-scenario CUDA small campaign executes and passes release qualification.
- [x] The 41-scenario CUDA standard campaign executes and passes release qualification.
- [x] The 41-scenario CUDA massive campaign validates with two non-overlapping assignments and a checksummed release binding.
- [x] Machine A's complete 20-scenario/12,368-item CUDA preflight says `READY_TO_LAUNCH`.
- [x] A real six-case CUDA rehearsal proves execution, status, controlled stop, assignment resume, export, transfer validation, merge, and analysis.
- [x] A bounded CPU campaign run proves the CPU executor path after CUDA integration.
- [x] Relevant tests, Ruff, mypy, PowerShell parsing, CPU/CUDA `pip check`, Markdown consistency, DOCX generation, and rendered-page QA pass.
- [x] Raw datasets, model caches, environments, runtime databases, secrets, and large run output are excluded from Git.

## Release identity

- [ ] Both physical workers have cloned the same published `handoff` commit.
- [ ] Both setup reports name the same selected campaign mode.
- [ ] Both launch preflights print `release binding: PASS`.
- [ ] Both release bindings name the current `git rev-parse HEAD`, the same campaign manifest hash, and matching launch-package hash.
- [ ] Machine A assignment is 20 scenarios; Machine B assignment is 21; overlap is zero; union is all 41.
- [ ] Both operators selected CUDA campaign `campaign_06_massive_release_cuda`, or both explicitly selected CPU campaign `campaign_05_massive_release`.
- [ ] The matching standard release-qualification artifact exists and has `passed: true`.

## Machine A launch-day checks

- [x] Final acceptance proved Windows 11, RTX 3080 with 10,240 MiB VRAM, driver 610.62, Python 3.12.7, PyTorch 2.11.0+cu128, CUDA 12.8, and FFmpeg 8.1.2.
- [x] Final acceptance proved all Machine A models, sources, bounds, Dining/Restaurant RIRs, output location, RAM, and estimated disk reserve.
- [ ] Rerun immediately before launch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
```

- [ ] Confirm `READY_TO_LAUNCH`, 20/20 scenarios, 12,368 items, and zero blockers.

## Machine B required checks

- [ ] Machine B has physically run setup; no Machine A profile is being reused as proof.
- [ ] Authorized AMI, CHiME-6, CMU Arctic, HiFiTTS, LibriSpeech, VOiCES, Dining RIR, and Restaurant RIR assets resolve on B.
- [ ] The selected CPU or CUDA environment passes `pip check` and real evaluator verification.
- [ ] For CUDA, B reports its actual GPU and records nonzero evaluator VRAM; no CPU fallback occurred.
- [ ] B output is writable and free disk exceeds its estimated 2.47 GB artifacts plus 5 GiB reserve.
- [ ] B preflight says `READY_TO_LAUNCH`, 21/21 scenarios, 13,430 items, and zero blockers.

Machine B physical qualification is the only current external launch blocker. Optional Pyannote, Falcon, NeMo, WeNet, and Bedroom RIR work is not required.

## Execute and control

- [ ] Machine A runs `launch_worker.ps1 -MachineId machine_a -Device cuda`.
- [ ] Machine B runs `launch_worker.ps1 -MachineId machine_b -Device cuda`.
- [ ] Each operator confirms assignment-scoped status with `worker_control.ps1 -Action status`.
- [ ] If stopping, record the reason and use the same machine ID for assignment-scoped resume.
- [ ] Every worker scenario finishes `succeeded` or `succeeded_with_warnings`; no invalid, terminal failure, timeout, OOM, or unresolved temporary file remains.

## Export, transfer, merge, and report

- [ ] Each operator runs `export_worker.ps1` only after its assignment is complete.
- [ ] Both transfer manifests validate and report zero unexported scenarios.
- [ ] Copy only `transfer_packages/campaign_06_massive_release_cuda/machine_a` and `machine_b` to the coordinator.
- [ ] Coordinator merge validates checksums, reconciles all 41 IDs, and reports zero missing or conflicting duplicate.
- [ ] Coordinator analysis uses `campaign_04_standard_release_cuda/analysis/report/release_qualification.json` as prerequisite evidence.
- [ ] Final report exists at `automated_runs/campaign_06_massive_release_cuda/analysis/report/campaign_report.md`.
- [ ] Archive the campaign manifest, assignments, release binding, transfer manifests, merged index, release qualification, and final report together.

## Launch authorization

Authorize the two-machine run only when every unchecked item above the execution section is completed. Do not edit frozen manifests to bypass a failure; correct the stated machine/data condition and rerun setup or verification.
