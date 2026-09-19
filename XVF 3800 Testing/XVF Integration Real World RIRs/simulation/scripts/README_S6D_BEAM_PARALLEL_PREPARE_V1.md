# Four held accuracy worker queues

`s6d_beam_parallel_prepare_v1.py` partitions an exact, unapproved, fully bound stage queue into four disjoint worker queues. It preserves original native jobs, audio, capture/profile/galleries, model source/weights, source pacing, timeouts and full-input/closure evidence. Only protocol/state paths and queue grouping change. It also writes exact four-way membership for the declared528 additional stream diagnostic tasks, without fabricating their pending capture bindings.

Inputs: `--queue` and its exact `--queue-sha256`, the original `--plan` declaration and fresh `--output` directly under the report's runner folder. The original queue must be unapproved and every native/protocol output fresh. Output: four worker folders with `QUEUE.json` and empty-approved-list `APPROVAL_PROPOSAL.json`, a source-bound receipt, and `DIAGNOSTIC_528_WORKER_MEMBERSHIP.json`. C12 splits3perworker; the full528 diagnostics split132perworker after their actual capture manifests are bound. No sources, audio, parent proposals or models are modified or launched.

At most4 NN workers **total across all S6D accuracy studies**, including full-bank892 and beam work. Root alone assigns slots. The accepted runtime still fixes all workers to the common logical CPU pool12,13,14,15 with inner pools1; no wider affinity is invented. This is concurrent coverage/accuracy work, not a controlled latency benchmark. Latency findings require separately admitted serial runs. Do not overlap admitted serial176/Tk/host timing sessions. Keep all observed resource/queue delays, but do not report concurrent delays as latency benefits.

The fixed96 beam-core jobs may use the same metadata splitter only after their actual disjoint C selector calibration is accepted. Collection C12 uses disabled selectors. No Q thresholds are selected. Root must choose these parallel queues or the parent serial queue, never both. Each job appears exactly once and retains its original source-context and native output path. Empty approved-job lists and fresh paths are not execution permission; root must review and bind admission separately.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_beam_parallel_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_parallel_v1_checks'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_beam_parallel_prepare_v1.py" --queue "$r\runner\beam_C_queue_proposed_v2\QUEUE.json" --queue-sha256 '<exact queue SHA256>' --plan "$r\application\beam_execution_predecl_v3\PROSPECTIVE_PLAN.json" --output "$r\runner\beam_C_parallel_proposed_v1"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_beam_parallel_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_parallel_v1_checks"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_beam_parallel_prepare_v1.py" --queue "%R%\runner\beam_C_queue_proposed_v2\QUEUE.json" --queue-sha256 "<exact queue SHA256>" --plan "%R%\application\beam_execution_predecl_v3\PROSPECTIVE_PLAN.json" --output "%R%\runner\beam_C_parallel_proposed_v1"
```

For bound full diagnostic stages, supply their exact held parent queue and use a fresh output name. The tiny checks verify exact-once membership/order for12 and528 plus duplicate/empty rejection; they write only small G fixtures. They do not start a supervisor or alter actual CPU affinity.
