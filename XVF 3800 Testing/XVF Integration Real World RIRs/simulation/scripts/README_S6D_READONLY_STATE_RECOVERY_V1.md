# Getter-only review of S6D restoration state

Purpose: verify the actual current device configuration after the first bank pre-QA owner's strict snapshot restoration failed. The recorded difference was only autonomous current PP_AGCGAIN after an immediately verified exact restoration request. This helper uses a separately root-reviewed pure policy, preserves the original FAIL, and does not set parameters, reset the device, open audio, or authorize capture by itself.

Inputs: exact root source review containing this helper/README, the pure restoration policy, existing vendor/control dependencies; original batch initial_state/restoration/bridge failure; original supervisor identity; recorded output-disconnection acknowledgement. It proves the old owner and supervisor are absent, recorder service ports are idle and the hardware lock can be acquired before reading the full identity, static settings and ancillary getters. Any mismatch outside the explicit policy fails. The original immediate setter proof is bound; no new setter or exact restoration of hidden adaptive history is claimed.

Outputs: fresh `reports/S6D/20260913T195357Z/hardware_state_recovery_v1/RESULT.json` plus command logs, actual readback, both old and fresh policy decisions, source hashes and lock closure. After successful lock release it also writes `RECOVERY.json`, in the V5 owner's explicit reviewed-recovery schema. The old failed result, supervisor guard and ledger remain unchanged. Root must bind this new receipt explicitly in a new admitted owner/queue epoch; never silently resume the failed old queue. The read-only call adds no physical playback attempt.

PowerShell, only after the named root source review exists:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_readonly_state_recovery_v1.py" --source-review "$sim\reports\S6D\20260913T195357Z\capture_restoration_review_v1\ROOT_SOURCE_REVIEW.json"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_readonly_state_recovery_v1.py" --source-review "%SIM%\reports\S6D\20260913T195357Z\capture_restoration_review_v1\ROOT_SOURCE_REVIEW.json"
```

An existing output directory is refused; a subsequent review needs an explicitly fresh `--output` path under the same report tree. Use the existing Anaconda runtime for the vendor interface. Preserve all failures and never use a policy tolerance to conceal a static configuration change, missing immediate proof, disabled-AGC mismatch or invalid gain. This helper installs no recurring process or automation.
