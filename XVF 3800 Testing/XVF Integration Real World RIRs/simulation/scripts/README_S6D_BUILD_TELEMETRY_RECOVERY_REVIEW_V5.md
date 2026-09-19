# Record the root's B3 recovery review

Purpose: bind the reviewed V5 recovery and ownerV10 source graph, exact recorded telemetry failure, independent review and25 focused checks into an immutable root restoration authority. This metadata-only builder verifies files and invokes the helper's file-only input validator. It performs no process/device query, reset, setter, audio playback or model call.

Inputs: fixed recovery source proposal ace2b9be, its26 canonical execution dependencies and historical producer graph; the exact independent review path/SHA supplied by root; current complete ROOT_PROCESS_SNAPSHOT.json in capture_telemetry_recovery_v2; preserved original B3 ledger/owner/initial configuration/admission/failed capture data and11 telemetry files; and the existing confirmed disconnected-output record. Root must first review the actual source diffs and independent findings. Existing authorities/output paths are refused.

Outputs: runner/capture_owner_v10_source_v1/SOURCE_FREEZE.json, capture_telemetry_recovery_v2/ROOT_SOURCE_REVIEW_V5.json and ROOT_SOURCE_INPUT_VERIFICATION_V5.json. These bind exact original/configured identity recovery while preserving the historical process-exit-unproven FAIL. They do not claim actual restoration, new queue admission or scientific acceptance.

PowerShell, after root review and the actual current control snapshot:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_build_telemetry_recovery_review_v5.py" --independent-review 'ACTUAL_REVIEW_PATH' --independent-sha256 'ACTUAL_REVIEW_SHA256'
```

Anaconda Prompt / Windows CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_build_telemetry_recovery_review_v5.py" --independent-review "ACTUAL_REVIEW_PATH" --independent-sha256 "ACTUAL_REVIEW_SHA256"
```

Actual restoration is a later root action using the frozen V5 helper and exact generated authority/hash, with fresh process/TCP/lease/identity checks. It must respect the current experiment allocation and must never run concurrently with another hardware owner. See README_S6D_CLOSED_TELEMETRY_RESTORE_V5.md for inputs, outputs and exact execution commands. All failures, original source epochs, hardware480/21600/40GiB caps, disk floors and the original deadline remain unchanged.
