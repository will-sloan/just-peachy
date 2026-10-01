# Offline acceptance — NOT PASSED
No final persistent Nemotron release is accepted. Local models and a successful network-connected native run do not establish offline startup or recovery. The current result is INCOMPLETE.

The user reconnected power/Ethernet and a new Linux boot was observed. The baseline auto-started capture; normal Stop closed it and normal Settings saved auto_start_listening=false. This does not prove final-candidate coldboot behavior. Display270 was observed on the returned baseline.

## Remaining release acceptance
1. Install one versioned manual frontend with finite production policy, explicit supported modes and idle startup.
2. Verify complete independent code/config/data backup and a local rollback/recovery path.
3. Launch each real profile shortcut; verify duplicate-owner exclusion, correct pins and capture off.
4. Restart the final app locally and verify saved settings, display and hardware availability.
5. Only after recovery works, exercise the supported mode with external networking unavailable. Record software denial separately from physical Ethernet disconnection.
6. Perform one bounded recording, Stop/drain/Save/reopen and verified later PC copy. Check complete source samples/events, resource floors and release ownership.
7. Record actual physical touch and coldboot observations separately. Do not invent these from screenshots or process receipts.

All seven are final-release gates. Existing isolated/scoped passes may be reused where unchanged, but do not fill missing integration evidence. Physical/noisy tests must use consented participants and FIELD_VALIDATION.md after functional acceptance.

No network isolation or reboot was attempted during finalization. Original app remains the recoverable baseline; it is not relabelled the new offline release.
