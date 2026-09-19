# Remaining bank V6 after the failed replacement pre-QA

Purpose: prepare a fresh root-admitted continuation only after separately reviewed V6 recovery and ownerV11 source. This is an additive derivative of V5. It keeps all121 historical charged attempts (118PASS/3FAIL), all54 uncompleted stages and all312 pending rows. It renames only failed QA_P_MAIN6_B3_PRE_R2 to a fresh QA_P_MAIN6_B3_PRE_R3, preserving source/profile/gain/guard/timing. The unstarted04_19_R2 retry remains unchanged. The forecast is433 attempts and19,818.0819375 charged seconds.

Required inputs: exact interrupted bank_queue_v5 admission2f79e425,121-entry ledger, REPORT_BLOCKED checkpoint with no completed stages and the failed pre-QA active identity; retained18 transport review4322d76b; actual root V6 source review; a root-bound combined V11 execution freeze/hash with28 collision-free canonical dependencies; and a successful actual new QA recovery receipt. The frozen V11 prior_closure validator must prove all inherited recoveries and the new failure before the first output. A pending recovery is not accepted.

Outputs, only when root runs with actual accepted inputs: fresh runner/bank_queue_v6,18 plans/authorizations,54 jobs, owner check-plan logs, literal APPROVAL and ROOT_QUEUE_REVIEW. This tool does not launch playback. Existing output, protocol or payload destinations are refused. The preliminary metadata proposal is separate and contains no actual recovery binding or approval.

All480-attempt/21600-second/40GiB caps, C50/G75 floors, original72-hour deadline/45-minute reserve, watchdogs and full-source guards remain unchanged. Source graph, prior failures and18 transport-only retention are explicit; no retrospective QA or whole-batch PASS is inferred.

PowerShell root-only future admission (do not run placeholders):

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_bank_remaining_admit_v6.py" --source-review 'ACTUAL_ROOT_REVIEW.json' --execution-freeze 'ACTUAL_COMBINED_FREEZE.json' --execution-freeze-sha256 'ACTUAL_FREEZE_SHA256' --recovery 'ACTUAL_QA_RECOVERY.json'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_bank_remaining_admit_v6.py" --source-review "ACTUAL_ROOT_REVIEW.json" --execution-freeze "ACTUAL_COMBINED_FREEZE.json" --execution-freeze-sha256 "ACTUAL_FREEZE_SHA256" --recovery "ACTUAL_QA_RECOVERY.json"
```

No authority or actual recovery is created by this source preparation. Root separately reviews the eventual literal admission and current ownership/resources before launch. Historical B1/B2 closure is inherited through old admission evidence; the immediately previous failed bankV5 contributes zero completed stages.
