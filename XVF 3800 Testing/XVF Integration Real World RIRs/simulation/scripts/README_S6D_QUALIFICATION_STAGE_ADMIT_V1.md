# Admit one S6D qualification stage

Purpose: materialize one exact already reviewed qualification stage from the existing physical proposal. This helper does not access hardware, launch processes, or advance on an unreviewed result. It preserves the previous first-QA queue and its documented `progress_count` predicate error; capture counts use `semantic_checks.attempt_count`.

Inputs: stage index 1–5, the root acceptance of the new census runner, the actual preceding-stage review, the immutable original capture proposal/source graph, current global ledger, recorded user output-disconnection confirmation, and existing limits. Stage 1 requires the exact accepted first-QA receipt; later stages require a root review authorizing that next stage index.

Outputs: a new `reports/S6D/20260913T195357Z/runner/qualification_stage_N_queue_vV` directory with literal queue, approval, one-stage capture plan, authorization, safety binding and preparation receipt. `--admission-version V` defaults to1; append `--admission-version 2` to the examples below for stage1 because the first validation was rejected before launch for placing long calibration WAVs in the runner's small-source list. The preserved old queue contains the exact old helper and rejection. Audio remains exact hash-bound in the capture plan and is validated by the owner; the runner repeatedly checks small code/configuration only. Existing directories/attempt IDs are refused. Raw outputs remain in the capture plan's declared G drive locations. The owner charges all attempts before playback and restores its recorded initial settings after closure.

PowerShell (stage 1 example):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_qualification_stage_admit_v1.py" --stage 1 --runner-review "$sim\reports\S6D\20260913T195357Z\runner\source_epoch_census_v4\ROOT_SOURCE_ACCEPTANCE.json" --predecessor-review "$sim\reports\S6D\20260913T195357Z\physical_first_QA_review_v1\ROOT_ACCEPTANCE.json"
```

Anaconda Prompt / CMD (no environment activation needed):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_qualification_stage_admit_v1.py" --stage 1 --runner-review "%SIM%\reports\S6D\20260913T195357Z\runner\source_epoch_census_v4\ROOT_SOURCE_ACCEPTANCE.json" --predecessor-review "%SIM%\reports\S6D\20260913T195357Z\physical_first_QA_review_v1\ROOT_ACCEPTANCE.json"
```

Root next performs both runner and owner validate-only calls, then records the exact launched command in that queue's README_RUN.md. Never terminate a hardware process. Cooperative STOP, actual restoration and closed owner/supervisor receipts are required before proceeding. No heavy native inference is admitted during the observer comparison. PC peripherals may remain connected; the existing user confirmation applies to the XVF's own analog outputs. Storage floors C50GiB/G75GiB, payload40GiB,480 attempts,21600 charged seconds and fixed campaign deadline remain enforced.
