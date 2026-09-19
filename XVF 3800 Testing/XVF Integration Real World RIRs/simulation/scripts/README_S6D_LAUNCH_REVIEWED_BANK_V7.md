# Launch separately admitted V7 hardware continuation

Purpose: adapt the reviewed V6 launch procedure to a separately root-admitted V7 queue and independent literal review. Existing V6 launcher helpers are hash-pinned; original V4 supervisor, C12 authority, source guards, allocation checker, hidden launch, keep-awake, disk floors, physical40GiB cap and deadlines remain. This script does not admit or rewrite capture plans. Source preparation does not call this entry point.

Use the new serialization-corrected V7 source freeze and `bank_v7_preparation_v2` admission. The preserved73d71175/255c5cf7 source/preparation epoch is not admissible because its inherited Windows text writer changed virtual LF hashes. Only the V7 admission helper's local writer changed; this launcher source and its runtime checks are unchanged, and the new freeze binds the updated helper plus this launcher together. Launch receipts are hashed after writing and are not virtual-bound documents.

Inputs: actual V7 `ROOT_QUEUE_REVIEW.json` path/SHA, independent literal review path/SHA with status `PASS_INDEPENDENT_LITERAL_BANK_REVIEW` joining exact root receipt/queue/approval, and actual C12 acceptance path/SHA. The admitted source freeze must contain both maintained V7 helper and launcher. The original V6 interruption receipt must remain exact. At actual launch, a new complete process inventory and pinned6730 allocation decision recheck absence of all known C12 and V6 owners and competing NN/device workloads; old snapshot freshness is never reused.

Outputs: fresh `runner/bank_queue_v7/ROOT_LAUNCH_PREFLIGHT.json`, `ROOT_LAUNCH.json`, stdout/stderr logs, and the existing V4 supervisor's state at `G:/Just_Peachy_S6D/20260913T195357Z/runner/bank_queue_v7/supervisor_state`. The supervisor performs its original fresh shared census before hardware. Existing state/launch paths are refused. No forced device/process recovery is added. Final scope is54 stages/318 future attempts,463 total/21187.3213125 charged seconds. Fresh26-case recaptures seek their own QA-qualified coverage; old transport-only records receive no retrospective credit. Physical40GiB, C50/G75 and the original deadline/reserve remain.

PowerShell / Anaconda PowerShell Prompt, root only after admission and independent literal review:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$run="$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_launch_reviewed_bank_v7.py" --bank-admission "$run\runner\bank_queue_v7\ROOT_QUEUE_REVIEW.json" --bank-admission-sha256 '<actual admission SHA256>' --independent-review '<actual independent literal review path>' --independent-review-sha256 '<actual independent SHA256>' --c12-acceptance "$run\runner\beam_C_queue_proposed_v4\ROOT_ALL12_ACCEPTANCE.json" --c12-acceptance-sha256 '6d02b3fdd9c27bfe4b2372478176de17cd99c9f32c17885c26f1c2cc65119725'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "RUN=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_launch_reviewed_bank_v7.py" --bank-admission "%RUN%\runner\bank_queue_v7\ROOT_QUEUE_REVIEW.json" --bank-admission-sha256 "<actual admission SHA256>" --independent-review "<actual independent literal review path>" --independent-review-sha256 "<actual independent SHA256>" --c12-acceptance "%RUN%\runner\beam_C_queue_proposed_v4\ROOT_ALL12_ACCEPTANCE.json" --c12-acceptance-sha256 "6d02b3fdd9c27bfe4b2372478176de17cd99c9f32c17885c26f1c2cc65119725"
```

Do not run placeholders. No environment activation or installation is required with the exact interpreter. A launched or completed transport queue does not by itself complete scientific qualification or S6D. Preserve all original failures, provisional-case limitations, and the separately held native/composite-closure requirement.
