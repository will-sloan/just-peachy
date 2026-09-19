# Conditional remaining S6D native confirmation preparation

Purpose: create DATA-ONLY proposals for 892 remaining repaired GUIv3 C065/C088 full-bank routes, conditional on retention of those exact candidates and root acceptance of all 68 distinct repaired native176 routes. It preserves all 960 historical original control predictions through the source/receipt audit. It does not run native inference, scoring, hardware, device queries, or an approval/admission operation, and never edits active176.

Inputs: immutable source-audited S6C full240 input/profile/gallery bindings, S6D cache scope audit, native176 repaired manifest and reviewed protocol/queue template, scene metadata for prospective pilot selection, and measured historical pilot payload/runtime findings. The helper uses the Python standard library. Source metadata/hashes are read; raw audio/model weights/journals and active outputs are not read. Actual jobs retain full waveform/model/source verification and whole-input guards.

Outputs: a small R preparation receipt and forecast; G contains the conditional 960=68+892 matrix, four immutable 223-job manifests, four 4-cell pilot queue proposals (16 total), and four 219-cell continuation queue proposals (876 total). Each worker owns one exact candidate/tap. Its first four cases are selected solely from original scene metadata: short complete replies, overlap, a100-second long-return scene, and instrumental nonspeech; all other remaining cases follow lexically. Every pilot cell is part of the 892, with no duplicate pilot rerun. Accepted credits remain zero in this preparation. Runtime/native/protocol/state output directories are not created.

No APPROVAL.json or ROOT_ADMISSION.json is produced. APPROVAL_PROPOSAL.json has an empty approved-job list. ROOT_ADMISSION_PROPOSAL.json is explicitly NOT_ADMITTED and records unresolved prerequisites. Root must create a new exact adoption after source/matrix and actual native176 acceptance review. Missing/rejected native176 credits require a fresh metadata epoch; never silently drop them or select favorable repeats.

PowerShell — prepare data only:

```powershell
$taskSim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$taskSim\scripts\s6d_native_remaining_prepare_v2.py" --output "$taskSim\reports\S6D\20260913T195357Z\runner\native_remaining892_preparation_v2" --payload 'G:\Just_Peachy_S6D\20260913T195357Z\runner\native_remaining892_preparation_v2'
```

Anaconda Prompt / CMD — prepare the same data only:

```bat
set "TASK_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%TASK_SIM%\scripts\s6d_native_remaining_prepare_v2.py" --output "%TASK_SIM%\reports\S6D\20260913T195357Z\runner\native_remaining892_preparation_v2" --payload "G:\Just_Peachy_S6D\20260913T195357Z\runner\native_remaining892_preparation_v2"
```

Existing output roots are refused. Preserve any previous preparation and use a new explicit versioned R/G pair for later data changes. No installation, copying of PCM/model corpus, automatic experiment resumption, or new persistent process is needed.

The reviewed wrapper is unchanged. All workers share logical CPUs12,13,14,15; each ASR/speaker/punctuation model pool retains one thread. Four concurrent workers mean four full model stacks and multiple competing lanes on four shared logical CPUs, not physical core isolation or four threads total. Root must enforce a TOTAL maximum of four NN workers across these and the beam queues, never four plus four. The existing runner has per-state-directory ownership; this metadata adds no inter-queue semaphore. Each queue remains serial with a distinct state/protocol/output path.

Keep native176/Tk/HOST controlled timing runs serial and separate. Parallel results are confirmation/accuracy and descriptive throughput/resource evidence only, not the serial latency comparison or a CM5 benchmark. No physical observer comparison may overlap without the root's explicit allocation. Native cell180s, supervisor360s, stall180s, heartbeat45s and stop grace75s are inherited unchanged. Root first admits only the four 4-cell pilot queues, reviews actual throughput, memory, failures, complete-source and closure evidence, then decides whether the four continuations are feasible. A watchdog failure is preserved; do not extend limits silently.

After root adoption only, inspect one exact selected group with PowerShell:

```powershell
$taskR='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6D\20260913T195357Z'
$taskPlan=Get-Content -Raw -LiteralPath "$taskR\runner\native_remaining892_preparation_v2\PREPARATION_RESULT.json" | ConvertFrom-Json
$taskGroup=$taskPlan.groups | Where-Object { $_.group -eq 'worker_1_pilot' }
$taskGroup | Format-List
```

After actual root approval/admission files exist, the exact inherited runner's validate-only command is:

```powershell
$taskApproval=$taskGroup.approval_path
$taskQueueHash=(Get-FileHash -Algorithm SHA256 -LiteralPath $taskGroup.queue.path).Hash.ToLowerInvariant()
if ($taskQueueHash -ne $taskGroup.queue.sha256) { throw 'Reviewed queue changed' }
$taskApprovalHash=(Get-FileHash -Algorithm SHA256 -LiteralPath $taskApproval).Hash.ToLowerInvariant()
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B $taskPlan.runner.path --queue $taskGroup.queue.path --queue-sha256 $taskQueueHash --approval $taskApproval --approval-sha256 $taskApprovalHash --state-dir $taskGroup.state_dir --validate-only
```

CMD users can run `powershell -NoProfile` and paste the same inspection/validation blocks. Select worker_1_pilot through worker_4_pilot individually. Continuations remain unapproved until the actual pilot review and slot allocation are accepted. Only root may replace `--validate-only` with `--keep-awake` for an explicitly admitted launch; no launch script is generated here.

Every queue retains C>=50GiB, G>=75GiB, the same three logical payload roots and shared40GiB cap, and the September16 19:53:57Z hard end with45-minute closeout reserve. FORECAST.json distinguishes measured single-cell pilot inputs from unmeasured arithmetic four-worker estimates. Existing campaign payload, metadata, new logs, scoring and remaining physical/beam work must all fit; the pilot is a feasibility gate, not permission to reduce storage or safety constraints.

V2 replaces the redundant ambience-overlap pilot stratum with the first remaining100-second F06 scene. The twelve99.6954375-second native inputs make this relevant to the unchanged180-second native timeout. All892 cells and source/settings are identical toV1; only pilot/continuation order and source-length-scaled forecast arithmetic change. V1 remains unapproved and is preserved.
