# Failure-aware host review V2

Purpose: finish independent review/backup of the immutable V1 host run after the V1 reader rejected its worker affinity. All19 file-publication cases passed and the owned worker naturally exited0, but actual worker affinity was [4,14] while admission requested [14]. The job's read-back affinity mask was [4,14]. The cause of the narrower process request not persisting is not proven. The whole trial does not pass its requested worker envelope; no failed claim is retroactively changed. No worker/test is rerun.

Inputs: existing field-host-budget-v1-evidence ADMISSION, RESULT, LAUNCH, owner and exact pinned code/README plus all private fixtures. V1 review failed before any backup or review mutation. This new reader sets and verifies its ownCPU14 before reading. It saves a mapped review failure receipt with requested/observed affinity, verifies exact worker death/job closure, copies small fixture payloads byte-for-byte with the new bounded API, then publishes a scoped review and logical_success=false closure. The original V1 reader, result, launch/admission and README are unchanged. Inputs remain private; no target/model/catalogue data are recopied.

Outputs: host/failure/review.raw and review-failure.json, host/metadata/BACKUP.json and REVIEW.json, host/closure/review-closure.json, verified-fixture-backup/. Fixture .pending bytes are retained at their original path and backed up under explicitly mapped .partial-evidence names. No cleanup/delete/reset, new source/model/Pi job/capture/GUI or full field acceptance. Future live use requires a fresh launcher that applies and reads back the intended job/process affinity before reads; this review is not that qualification.

Run once; it requires completed V1 and absent V2 publication names. No separate worker dispatch.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_host_budget_v2.py
```

## Command Prompt / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_host_budget_v2.py
```
