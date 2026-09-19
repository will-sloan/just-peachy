# Independent S6D bank metadata review and queue proposal

`s6d_bank_queue_prepare_v1.py` independently checks root's prepared bank against the exact original MAIN/SCAN/repeat, E and physical continuous authorities. It then writes a data-only literal queue for 20 groups, each with separate pre-QA, body and post-QA owners. It does not import the capture owner, open a device, run models, launch a supervisor, or create approval.

Inputs are `physical_bank_preparation_v1/PREPARATION_RESULT.json`, its 20 group plans, original authorities and the 62-file root adoption map. The source graph comes from the accepted V4 owner/bridge and census V4 runner already bound in `runner/qualification_stage_1_queue_v2`. The actual safety acknowledgement is copied as existing evidence; actual MAIN/SCAN qualification and whole-bank admission remain pending. No active sources or historical plans are changed.

The audit compares full ordered mappings, original source path/size/hash tuples, E/continuous frames, exact profiles, roles, pre/post-QA sentinel bytes, inherited policies, reset/telemetry settings, 302 root verification receipts and rational playback charges. It intentionally does not rehash or reopen 3 GB of WAVs: the root builder's whole-file/header/finiteness/peak checks remain inherited evidence. Results are 240 MAIN +48 SCAN +4 fixed repeats +60 E +2 uninterrupted 900-second physical sessions +40 QA =394 attempts. With the existing 33 qualification attempts the original forecast is427 attempts and19670.0340625 charged seconds. Failures/retries still consume the actual shared ledger allowance.

PowerShell, metadata only:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_bank_queue_prepare_v1.py'
```

Anaconda Prompt or CMD, no activation:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_bank_queue_prepare_v1.py"
```

The default fresh output is `reports/S6D/20260913T195357Z/runner/bank_queue_preparation_v1`. `--output` may name another fresh child of the same runner directory; existing output is refused. Outputs are an independent review receipt, 20 proposed plan/authorization pairs, `QUEUE_PROPOSAL.json`, an empty `APPROVAL_PROPOSAL.json`, and `QUEUE_PREPARATION_RECEIPT.json`. The helper performs only the frozen runner's pure `validate_queue` in memory to check schema/source/output bindings, and confirms the saved empty approval rejects. It never constructs an approved file. No further waveform or broad model-free suite is needed for this metadata construction.

Group plans contain 32 attempts for each MAIN group; 16/15/14/15 for SCAN;12 for each E group;3 for each continuous group. Each of the 60 child commands includes only its three-stage group's plan. The existing bridge and owner validate that bounded group, so they do not rehash all394 inputs before every child. Periodic source checks include small code/JSON only. Literal child argv arrays are in the proposal and point to accepted owner `be4a03f7`, bridge `2d1fa47c` and runner `fdffb4ca`.

Before root adopts a fresh executable queue, root must bind the actual accepted MAIN/SCAN physical stream, delay/tail, telemetry/observer and QA/restoration review to each plan/authorization; populate the actual ledger/budget observation; set authorization only for the reviewed exact plan and update all affected plan/auth/queue/job hashes. The supplied authorization has `root_review_passed=false` and each plan has `physical_qualification_review=null`. The supplied approval contains no approved job hashes. Both layers must remain unable to launch until root admission. Production validate/launch commands then use the adopted queue and approval, not these draft paths:

```powershell
& 'C:/Users/amiri/anaconda3/python.exe' -B 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6D\20260913T195357Z\runner\source_epoch_census_v4\s6d_runner_v1.py' --queue '<root-adopted QUEUE.json>' --queue-sha256 '<adopted queue SHA256>' --approval '<root-adopted APPROVAL.json>' --approval-sha256 '<adopted approval SHA256>' --state-dir '<fresh G runner state directory>' --validate-only
```

```bat
"C:/Users/amiri/anaconda3/python.exe" -B "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6D\20260913T195357Z\runner\source_epoch_census_v4\s6d_runner_v1.py" --queue "<root-adopted QUEUE.json>" --queue-sha256 "<adopted queue SHA256>" --approval "<root-adopted APPROVAL.json>" --approval-sha256 "<adopted approval SHA256>" --state-dir "<fresh G runner state directory>" --validate-only
```

After validation and root launch, the existing V4 code can advance through the immutable 60-job order without manual permission for each30-case group. It requires actual child exit, matching complete receipt, closed protocol observer without errors, every selected case's transport/telemetry proof, exact full submitted input extent, closed audio/writer, and verified owned restoration. Pre-QA additionally requires zero MIC mismatches and captured nonzero source payload; post-QA has the same predicate before the next group starts. `predecessor_job_id` is descriptive metadata; `queue.jobs` order plus V4's verified checkpoint logic enforces progression. On any failed predicate V4 stops and requests cooperative restore; it never kills hardware owners or skips a group. Resume revalidates completed artifact bindings.

The bridge checks durable file/ledger changes every second and writes heartbeats every5 seconds. These are bounded progress observations, not acoustic time or fabricated source progress. V4 uses its asynchronous bounded payload census and normal health loop. The 480-attempt/21600-second/40-GiB limits, C50/G75-GiB floors, unchanged September16 19:53:57Z deadline and45-minute closeout reserve apply throughout. LIMITED level-screen outcomes remain visible; transport PASS and pre/post-QA cannot by themselves prove processed route identity, tail completeness, clean audio or beam efficacy. Raw capture WAVs, gain, measured RIRs, source order and source clocks remain unchanged.
