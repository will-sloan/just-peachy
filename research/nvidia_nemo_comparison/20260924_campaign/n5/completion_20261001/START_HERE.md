# Offline Pi delivery and handoff

**Hard boundary: October 1, 2026, 13:42:44 Toronto / 17:42:44 UTC.** This is exactly 24 hours after the request was anchored at September30 17:42:44 UTC. It replaces the prospective17:47:34 UTC checkpoint; historical evidence remains unchanged.

Initial status: **IN_PROGRESS, not offline-ready yet.** Latest verified preparation: CHECK_SUMMARY_V97, mode-entry contract and factory wiring. Latest actual native application check remains V96 recovery. Separate V95 method-bound positive Start/Stop is retained. See current Git remote verification and PATHS_AND_BACKUPS; the mode launcher/live/offline release remain open.

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
