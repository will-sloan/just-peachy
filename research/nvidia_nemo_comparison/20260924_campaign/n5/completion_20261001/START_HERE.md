# Offline Pi delivery and handoff

Current V108: a bounded local streamed mirror verified75retained native-evidence files without loading the payload as a batch. Physical-path projection now accounts for configuration replacements, native/archive controls, pending files and guards under the unchanged target maximum. These are local-copy and preparation results; no Pi source/model/GUI ran. Actual Pi-to-host streaming, full runtime writer census and live D1 endpoint binding remain open. The launcher milestone remains missed; deadline unchanged. See FIELD_STREAMED_MIRROR_FINDINGS_V1 and CHECK_SUMMARY_V108.

**Hard boundary: October 1, 2026, 13:42:44 Toronto / 17:42:44 UTC.** This is exactly 24 hours after the request was anchored at September30 17:42:44 UTC. It replaces the prospective17:47:34 UTC checkpoint; historical evidence remains unchanged.

Status: **IN_PROGRESS, not offline-ready yet.** Latest visible inspection scope is CHECK_SUMMARY_V100 (passed); latest positive native model entry is V98. Streaming now passed the fresh-child launcher and coherent generic state path; other modes retain separate prior saved-app receipts. See PATHS_AND_BACKUPS and the current remote verification.

| Document | Purpose |
|---|---|
| [Completion plan](COMPLETION_PLAN.md) | Critical path, time boxes, acceptance and hard stop |
| [ChatGPT handoff](CHATGPT_HANDOFF.md) | What was explored, results, blockers and continuation instructions |
| [Mode guide](MODE_GUIDE.md) | Product modes, backend choices, buffering, costs and availability |
| [Offline acceptance](OFFLINE_ACCEPTANCE.md) | No-network operation, controls, deployment and rollback gates |
| [Field validation](FIELD_VALIDATION.md) | Future in-person noisy-environment test procedure |
| [Field run template](FIELD_RUN_TEMPLATE.json) | Copy into private storage for each actual field run |
| [Paths and backups](PATHS_AND_BACKUPS.md) | Consolidated locations, preservation and simplification map |
| [Acceptance status](ACCEPTANCE.json) | Required completion gates with evidence and open blockers |
| [Handoff packaging instructions](README_HANDOFF_TOOLS.md) | Purpose, inputs, outputs and PowerShell/CMD/Anaconda commands |
| [Deadline authority](DEADLINE_AUTHORITY_V1.json) | Exact new deadline and finalization rule |

Maintain this concise navigation layer as readiness changes. Older research documents and failed trials are retained as evidence, not copied into every guide. A final handoff must name the exact active release and launcher, enabled modes, acceptance receipts, backup checksums, recovery command and unresolved gaps.

At the boundary close owned research work and pause the automation. Desired final state: verified field app running idle with capture off. If an essential gate fails, leave the device recoverable and report delivery incomplete. A planning ZIP is not a deployable runtime or offline-readiness proof.
