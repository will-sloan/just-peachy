# Record the exact configured-state recovery review

`s6d_build_telemetry_recovery_review_v4.py` records root's completed review of the V4 recovery helper and V9 owner. Inputs are the exact source freezes,18 focused full-orchestration fixtures, prior V3 authority/failure and failed17 configuration. It verifies the source graph and native closure using existing file evidence. It performs no device, process, network, audio or model calls.

No arguments are needed: this run's paths and hashes are explicit. New immutable outputs are `ROOT_SOURCE_REVIEW_V4.json` and `ROOT_SOURCE_INPUT_VERIFICATION_V4.json` in `simulation/reports/S6D/20260913T195357Z/capture_telemetry_recovery_v1`. Existing outputs reject. Earlier sources, failures and charges remain unchanged.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_build_telemetry_recovery_review_v4.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_build_telemetry_recovery_review_v4.py"
```

Actual root-only restoration uses the resulting exact review/hash according to README_S6D_CLOSED_TELEMETRY_RESTORE_V4.md and a fresh `closed_telemetry_restore_v4` directory. That runtime must separately prove current ownership/listeners and actual restore/readback/lease closure. After actual PASS, README_S6D_BANK_REMAINING_ADMIT_V4.md describes new metadata admission with the final V9 freeze/hash, literal review and fresh QA. No hardware cap or floor changes are included.
