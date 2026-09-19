# Admit the expanded S6D capture bank

Purpose: adopt the independently reviewed 394-attempt bank only after the root has reviewed actual MAIN/SCAN routing, four exact microphone QA passes, processed lag/tails, telemetry observer effects and owner restoration. This is metadata preparation plus the owner's read-only `check-plan` action; it does not open audio, send device commands, or launch a capture. Existing proposals and captures remain unchanged.

Inputs: `runner/bank_queue_preparation_v1`, the actual root scientific qualification receipt supplied with `--qualification-review`, exact accepted owner/bridge/census V4 source bindings, the global physical ledger, original audio hashes, recorded XVF output-disconnection confirmation, resource limits and original campaign deadline. This version deliberately requires exactly 33 completed qualifying passes; retries or changed history require a new reviewed admission, never editing the ledger to fit.

Outputs: a fresh `runner/bank_queue_v1` with 20 admitted group plans and authorizations, 60 ordered pre-QA/body/post-QA jobs, exact job hash approval, 20 read-only owner validation logs and `ROOT_QUEUE_REVIEW.json`. Each case retains scientific limitations. A route qualification does not certify exact MIC recovery for processed-only scenes, perfect source timing, unclipped output, speaker identity, or beam efficacy. LIMITED streams remain recorded unchanged.

The bank is 240 MAIN scenes, 48 SCAN scenes, four matched repeats, 60 enrollment passes, two uninterrupted 900-second sessions, and 40 QA passes. Bank charge is 18664.8785 seconds; original whole-study physical forecast is 427 attempts / 19670.0340625 seconds. All actual failures remain charged. The queue checks resource floors C50GiB/G75GiB, total new payload40GiB,480 attempts/21600 charged seconds and original deadline; no new job after2026-09-16 19:08:57Z. Raw and mono payloads go to the declared G drive bank. Health and restoration records are local. Hardware is never forcibly terminated.

PowerShell, after the root creates the actual review file shown:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_bank_admit_v1.py" --qualification-review "$sim\reports\S6D\20260913T195357Z\physical_qualification_review_v1\ROOT_PHYSICAL_QUALIFICATION_V1.json"
```

Anaconda Prompt / CMD, no activation needed:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_bank_admit_v1.py" --qualification-review "%SIM%\reports\S6D\20260913T195357Z\physical_qualification_review_v1\ROOT_PHYSICAL_QUALIFICATION_V1.json"
```

After reviewing the generated receipt, the root launches the exact queue with `s6d_launch_admitted_queue_v1.py --review-receipt <bank_queue_v1/ROOT_QUEUE_REVIEW.json>`. That launcher performs runner validation; the 20 owner validations were already performed here. Its generated README records the historical command. Never run a second copy or overwrite prior outputs. No automatic Codex resumption is installed by these helpers; the runner writes local checkpoint requests and restores its own keep-awake state on closure.
