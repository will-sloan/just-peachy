# Admit a fresh S6D bank after reviewed restoration recovery

Purpose: materialize a fresh60-stage bank using the separately accepted capture ownerV5/bridgeV2. It preserves the earlier firstQA capturePASS and strict-restorationFAIL. The firstQA is repeated once as QA_P_MAIN6_B1_PRE_R2. All other pending physical inputs, profiles, gains, guards, case IDs and scientific limitations remain unchanged. This helper performs metadata work and20read-only owner check-plan calls; it opens no audio and issues no device commands.

Inputs: exact original bank_queue_v2 admission,34charged captures, original failed-owner ledger binding, root source review for the dynamic-gain policy and a successful getter-only RECOVERY.json. Before the first output, the helper loads the exact reviewed V5 owner and calls its file-only prior_closure gate with the explicit recovery binding. This recomputes the policy, original immediate proof and ownership/closure bindings; a PASS label alone is insufficient. The returned ledger must equal the bound34-pass ledger, whose bytes are rechecked before queue approval. That same binding and reviewed_recoveries list go into every owner authorization. It does not alter or silently override old failure receipts/guards. New collection still requires actual source/gain/route/integrity checks and eachnewowner's complete restoration under the explicit static-configuration/immediate-gain-request policy. The shared README_S6D_CAPTURE_V5.md documents both owner and bridge; no separate bridge README is required.

Outputs: fresh bank_queue_v3 with20plans,20authorizations,60serial preQA/body/postQA jobs, hash approval, validation logs and ROOT_QUEUE_REVIEW.json. Payloads remain in the declared G bank. Old jobprefix bank_v1 is replaced with fresh bank_v2 protocol/batch IDs; old outputs remain untouched.394future attempts plus34already charged produce428/19682.375375seconds, below480/21600. C50GiB/G75GiB/40GiBpayload and the original September16deadline remain enforced. No extra retry, reset, gain fit or timing extension is authorized by this helper.

PowerShell after the root source review and getter-only recovery exist:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_bank_resume_admit_v1.py" --source-review "$sim\reports\S6D\20260913T195357Z\capture_restoration_review_v1\ROOT_SOURCE_REVIEW_V2.json" --recovery "$sim\reports\S6D\20260913T195357Z\hardware_state_recovery_v1\RECOVERY.json"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_bank_resume_admit_v1.py" --source-review "%SIM%\reports\S6D\20260913T195357Z\capture_restoration_review_v1\ROOT_SOURCE_REVIEW_V2.json" --recovery "%SIM%\reports\S6D\20260913T195357Z\hardware_state_recovery_v1\RECOVERY.json"
```

After independent literal review, root may use s6d_launch_admitted_queue_v1.py with this new ROOT_QUEUE_REVIEW.json. Never start a duplicate or use oldfailedqueues. New queue acceptance explicitly requires policy validation, exactstaticmatch, verifiedimmediategainrequest and packed_input_disabled; it does not claim autonomousgain stayed constant. No-mutation aborts cannot satisfy actualcapturecompletion. Keep READMEs/receipts and failures. Root task continuation is separate; device safety remains local and hardware is never forcibly terminated.
