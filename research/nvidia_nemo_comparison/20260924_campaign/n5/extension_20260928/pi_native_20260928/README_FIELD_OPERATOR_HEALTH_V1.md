# Closed broker health V1

Purpose: inspect preserved native broker trees after normal closure or failure without constructing Ledger, Store, Controller, GUI, source or model. Expired policy is validated at its original issue time only for inspection. The result never authorizes writes, clears failure, resumes a consumed ledger or starts capture.

Inputs: exact native broker root and original RELEASE.json SHA256; its original pinned capsule must still exist. An independently admitted caller must announce/register its own real boot/PID/start ticks before project reads, set CPU3,128MiB hardAS,1MiB stack,FSIZE0 and a short alarm, and provide verified read-only module imports. The helper checks capsule pins, actual slot state, closed-receipt pins, every available stage/gate/broker/parent/child/source identity, current capture and both leases. Shared directory flock creates no file. Missing recorded identity remains a gap.

Output: bounded JSON-compatible dictionary. CLOSED_HISTORY_AVAILABLE requires all slots CLOSED, exact receipt checks, no active recorded identity/gap, captureoff and free leases. FENCED_PRESERVED includes incomplete/unused slots, active owners or identity gaps. Neither status is production restart permission. Audio payload/accuracy, native crash/powerloss, nonempty captions, cold boot and generic fault recovery are not qualified by this health check.

Native API, inside the separately admitted read-only caller:
    from field_operator_health_v1 import inspect_closed
    result = inspect_closed("/home/peachyprototype/JustPeachy/research/nemotron-20260928/EXACT-CLOSED-ROOT", "EXACT-ORIGINAL-POLICY-SHA256")

PowerShell, Command Prompt and Anaconda Prompt use the existing strict SSH route only through a reviewed registered caller. Do not run this native helper on Windows:
    ssh -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local
The API deliberately has no mutation or activation CLI. Required caller setup and exact source/module pins are part of its fresh admission; a bare SSH session is not an admission.

Manual broker capsule preparation, purpose, inputs, outputs and PowerShell/CMD/Anaconda commands are in README_FIELD_OPERATOR_MANUAL_V1.md. Its policy remains600s and baseline-bound. Persistent release policy, local supervisor, activation/rollback and restart wiring must be implemented and qualified separately.
