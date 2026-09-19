# V7 preparation and separate root admission

Purpose: create a reviewable exact B4 continuation from the preserved V6 interruption, then materialize fresh runnable V7 metadata only after explicit root acceptance. The helper reuses the existing base admission utilities, frozen V4 validator, ownerV11 prior-closure and check-plan gates. It changes no DSP, waveform, gain, guard, timing, control command, timeout, telemetry or restoration source.

Inputs: immutable B4 remainder/diagnosis, original V6 admission and28-source execution graph, unchanged145-entry ledger with141 PASS/four FAIL, and exact root interruption receipt `reports/S6D/20260913T195357Z/runner/bank_b4_root_closure_v1/ROOT_INTERRUPTED_EPOCH_ACCEPTANCE.json` SHA256 `7715b01db5d12634ea9ccd5b5a7cdf439a4e800e3fc8ab3c069dad8cae5ad06b`. The root receipt binds four completed stage validations, eight provisional case+metadata records, final failure/restoration/supervisor/lock and six closed process identities. It expressly does not complete V6 or apply later QA retrospectively.

Preparation writes only `PREPARATION.json` and `ROOT_REVIEW_PROPOSAL.json` in a fresh runner preparation directory. Proposed final artifact documents and their future hashes are embedded in the bundle; no runnable `CAPTURE_AUTHORIZATION.json`, `QUEUE.json`, `APPROVAL.json` or production batch is materialized. The root review proposal has `allow_admission=false` and no source-freeze binding. Embedded approval-shaped documents are review data, not actual authority files.

The serialization repair uses a V7-local exclusive binary writer for exactly `encoded(document)`, including proposed and materialized metadata, root admission receipt and final approval. This preserves the LF UTF-8 bytes used by `virtual()` on Windows. The inherited base writer is unchanged. Source freeze73d71175 and preparation255c5cf7 remain preserved as the rejected serialization epoch; use only the new source freeze and `bank_v7_preparation_v2`. No scientific, budget, closure, predicate or launch-allocation logic changes.

Actual admission requires a separately root-issued review with status `ROOT_ACCEPTED_EXACT_BANK_V7_REMAINDER_FOR_ADMISSION`, exact root thread/run, `allow_admission=true`, exact `preparation` and `original_epoch_closure` bindings, and the independently reviewed `source_freeze` binding. The freeze's `files` must include the exact maintained helper. Admission rebuilds and compares every proposed literal, rechecks root closure and all original source/ledger/recovery bindings, applies ownerV11 `prior_closure`, refuses existing destinations, and enforces the deadline and disk floors. It writes plans/authorizations/queue, performs the unmodified V4 validator against actual materialized paths, runs existing owner check-plan for18 groups, then writes root admission and `APPROVAL.json` last. A validation failure preserves partial metadata but produces no final approval; use a separately reviewed fresh recovery rather than overwriting. Preparation validates virtual bindings and unchanged policies; it cannot claim actual-path V4 validation before the files exist.

Final scope is18 groups/54 stages/318 future attempts,463 total,21187.3213125 charged seconds. Dedicated B3_RECAP18 pre/body18/post comes first; B4 pre/body30/post follows. All26 old partial scenes are freshly repeated for their own QA chain, with no duplicated unique-scene credits. Original290 and intermediate298 proposals remain immutable and are bound by final proposal `acffe3474cf00049a83183a73c10fb1ca52a6a85012dd53e9231109c0c2628d9`, based on independent scope supplement `fba2065070351a2f70723f4558ae37c3bd843116e665de56cef8c1e04f85496e`. Original V6 four completed stages/old partial evidence remain preserved. Same-profile45-second B3 case/metadata predicate pairs are cloned unchanged except exact case/attempt/source identities; all timing, signal, telemetry, route and metadata predicates stay. Caps remain480 attempts/21600 seconds/physical40GiB, C50/G75 floors, work deadline2026-09-16T19:08:57Z and final deadline19:53:57Z; headroom17 attempts/412.6786875 seconds.

PowerShell / Anaconda PowerShell Prompt (preparation only, after final source review):

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$run="$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_bank_remaining_admit_v7.py" --prepare "$run\runner\bank_v7_preparation_v2" --closure-review "$run\runner\bank_b4_root_closure_v1\ROOT_INTERRUPTED_EPOCH_ACCEPTANCE.json" --closure-review-sha256 '7715b01db5d12634ea9ccd5b5a7cdf439a4e800e3fc8ab3c069dad8cae5ad06b'
# Separate root action after reviewing the exact bundle and source freeze:
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_bank_remaining_admit_v7.py" --admit "$run\runner\bank_v7_preparation_v2\PREPARATION.json" --root-review '<actual root preparation acceptance path>' --root-review-sha256 '<actual SHA256>'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "RUN=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_bank_remaining_admit_v7.py" --prepare "%RUN%\runner\bank_v7_preparation_v2" --closure-review "%RUN%\runner\bank_b4_root_closure_v1\ROOT_INTERRUPTED_EPOCH_ACCEPTANCE.json" --closure-review-sha256 "7715b01db5d12634ea9ccd5b5a7cdf439a4e800e3fc8ab3c069dad8cae5ad06b"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_bank_remaining_admit_v7.py" --admit "%RUN%\runner\bank_v7_preparation_v2\PREPARATION.json" --root-review "<actual root preparation acceptance path>" --root-review-sha256 "<actual SHA256>"
```

No installation or environment activation is needed when using the exact interpreter. Do not execute placeholders. Preparation/admission never launch hardware; actual launch is the separate reviewed V7 launcher after independent literal queue review. Tk/HOST remains held until a future independently reviewed combined physical-coverage/closure gate is accepted; V6 never becomes retroactively FINISH.
