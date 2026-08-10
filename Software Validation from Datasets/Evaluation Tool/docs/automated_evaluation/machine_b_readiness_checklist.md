# Machine B readiness checklist

- [ ] Clone is from `https://github.com/will-sloan/just-peachy.git`, branch `handoff`.
- [ ] `git rev-parse HEAD` matches the final launch package; worktree has no unexpected changes.
- [ ] Python 3.12 environment was created on Machine B; `pip check` passes.
- [ ] `where.exe ffmpeg` and `ffmpeg -version` pass.
- [ ] `models/cache/whisper/base.pt` matches the frozen 145,262,807-byte SHA-256 identity.
- [ ] Every required dataset is local and readable; no source audio was copied into campaign folders.
- [ ] Dining and Restaurant RIR files match; Bedroom remains excluded without substitution.
- [ ] One real CMU Arctic Whisper Base run produced prediction, diagnostics, metrics, plots, and report.
- [ ] `machine_b_profile.json` was generated on Machine B, not copied from A.
- [ ] Full assignment preflight inspected exactly 21 scenarios and 13,430 item executions.
- [ ] Full assignment preflight reports `READY_TO_LAUNCH`, with enough RAM and at least 7.30 GiB free for run plus reserve.
- [ ] Assignment ID is `assignment_53642fa92b2a` and its frozen hash matches.
- [ ] Operator understands status, stop, assignment-scoped resume, export, and transfer commands.
- [ ] Coordinator received profile/preflight evidence and approved the provisional runtime balance.
- [ ] Small and standard release prerequisites passed before massive execution was authorized.

Any unchecked line keeps Machine B at `NOT_YET_TESTED` or `BLOCKED`.
