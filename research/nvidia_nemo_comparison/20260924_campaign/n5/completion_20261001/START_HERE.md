# Offline Pi delivery and handoff

Current V130: the new finite local-release contract passed three host fixture groups and seventeen rejects. It reserves complete independent recording, local-mirror and host-mirror capacity, blocks the next recording until closure and backup, and preserves failed/consumed slots across launch decisions. A bounded native metadata journal is prepared and backed up but has not run on the Pi. No production policy, lifetime extension, native application, capture, model or GUI was started this wake. V129 native read-only health and V128 two-session passes remain separate. Persistent local supervisor, actual local backup, activation/rollback and offline startup remain open. Hard deadline2026-10-01T17:42:44Z unchanged.

**Hard boundary: October 1, 2026, 13:42:44 Toronto / 17:42:44 UTC.** This is exactly 24 hours after the request was anchored at September30 17:42:44 UTC. It replaces the prospective17:47:34 UTC checkpoint; historical evidence remains unchanged.

Status: **IN_PROGRESS, not offline-ready yet.** V130 passed host finite-release contract checks and prepared the native journal. V129 read-only native health, V128 repeated sessions/history, V123 data actions and V98 positive saved Streaming remain separate. Persistent local operation and offline proof are still open.

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
