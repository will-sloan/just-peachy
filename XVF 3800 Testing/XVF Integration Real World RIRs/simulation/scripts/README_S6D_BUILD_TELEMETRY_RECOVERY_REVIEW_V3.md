# Record the packed-mode restoration adapter review

`s6d_build_telemetry_recovery_review_v3.py` records root's completed review of the narrow V3 restoration helper and V8 owner dependency update. Inputs are the exact frozen source graphs, 16 focused checks, previous V2 root authority and actual V2 pre-setter failure with released lease. The tests use the actual pinned Control parser/identity AST and saved getter replies. The adapter permits documented packed0/1 only before restoration; the post-restore microphone-mode check remains strict. No hardware, process, listener, model or playback operations are performed by this builder.

No CLI parameters are needed; this run's fixed evidence paths and hashes are explicit in the source. Outputs are new immutable `ROOT_SOURCE_REVIEW_V3.json` and `ROOT_SOURCE_INPUT_VERIFICATION_V3.json` in `simulation/reports/S6D/20260913T195357Z/capture_telemetry_recovery_v1`. Existing outputs reject. V1/V2 source reviews and actual failed restoration directories remain unchanged.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_build_telemetry_recovery_review_v3.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_build_telemetry_recovery_review_v3.py"
```

Actual root-only restoration follows `README_S6D_CLOSED_TELEMETRY_RESTORE_V3.md` using this exact review/hash and fresh `closed_telemetry_restore_v3` output. The builder does not authorize bypassing current ownership/process/listener checks or represent actual restored state. After verified real restoration, use `README_S6D_BANK_REMAINING_ADMIT_V3.md` with the exact final V8 freeze/hash, then review the generated literal queue and fresh QA. Physical40GiB,480attempts,21600chargedseconds and original floors/deadline remain unchanged.
