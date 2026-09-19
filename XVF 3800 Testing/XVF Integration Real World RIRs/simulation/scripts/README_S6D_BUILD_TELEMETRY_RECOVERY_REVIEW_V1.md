# Materialize the reviewed telemetry restoration authority

`s6d_build_telemetry_recovery_review_v1.py` records root's completed source review for the exact interrupted S6D bank. It verifies the frozen V6 owner, V2 logger, fresh restore helper, existing fixture receipts, 52-entry ledger, native telemetry files, original owner/bridge/supervisor evidence and prior user output-disconnection confirmation. It creates the immutable `capture_telemetry_recovery_v1/ROOT_SOURCE_REVIEW.json` and a file-only input verification receipt. This script does not inspect live processes, access hardware or launch playback. Its authority is specific to this reviewed failure and cannot be reused for another run.

Inputs are fixed local evidence paths and hashes in the source; no CLI parameters. Outputs live under `simulation/reports/S6D/20260913T195357Z/capture_telemetry_recovery_v1`. Existing outputs are never overwritten. Missing or changed evidence stops execution. Root has reviewed the sources and accepted the existing 34+23+11 fixture results; running this script alone is not a substitute for that review.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_build_telemetry_recovery_review_v1.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_build_telemetry_recovery_review_v1.py"
```

Actual restoration is a separate root-only execution described in `README_S6D_CLOSED_TELEMETRY_RESTORE_V1.md`, using the exact new review/hash. That helper repeats live process/port/lease checks, restores original exposed state and saves actual readback. Its old failure and charge evidence remain unchanged. Queue admission and fresh physical QA are additional steps; this builder does not perform them.
