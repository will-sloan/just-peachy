# Prospective S6D width scoring queue

This maintained README covers `s6d_score_queue_prepare_v1.py` and the copied
`README.md` in its output package. It prepares metadata and reads existing files
only. It does not import the scorer, run a model or hardware, launch a job,
modify the active width queue, create a production authorization, or create a
runnable runner approval.

Inputs: the exact upstream width queue, frozen scorer adapter plan V2,
independently accepted final scorer protocol wrapper, reviewed runner V3, and
a fresh output directory. The pinned analysis Python verifies NumPy 1.26.4 /
SciPy 1.13.1 / MeetEval 0.4.3 package metadata. The helper derives the prediction
index from the actual upstream queue and verifies all 3840 compressed prediction
files, exact 16-job/cell/tap paths and fixed 156/47/26/11 population counts.
This is read-only byte/coverage verification, not scoring or model-quality
interpretation.

Root accepted width semantic closure in
`angles/operational_width_v1/ROOT_WIDTH_CLOSURE_AND_SCORE_SOURCE_ACCEPTANCE_V1.json`
(SHA256 `5db5357af922256ac544286bee12c0047b2bcabb8ec70bbffb20ea6d9bce374f`).
This preparation verifies its exact index binding. The accepted final scorer
protocol remains SHA256
`f348ae09db926b519533e5380f54e64a4ab805af6585d2c3190958caa3e343e3`,
with 51 synthetic checks. No old graph or fixture campaign is rerun.

## Outputs

- `INDEX_VALIDATION.json`: actual index/hash/coverage result, compressed bytes
  verified, population counts and bound root width closure.
- `QUEUE_PROPOSAL.json`: literal scorer argv, output paths, environment,
  inherited deadline/C50/G75/40GiB floors, source bindings and result predicates.
  Its proposal schema is deliberately rejected by the runner.
- `APPROVAL_PROPOSAL.json`: executable/output allowlists; no approved job digest
  or final queue hash. It is deliberately not a runner approval.
- `ROOT_ADMISSION_RECIPE.json`: required authorization values and ordered root
  steps. `root_review_passed=false` is deliberate; this is not authorization.
- `source_epoch/`: identical scorer wrapper and its original README.
  The real scorer stays at its existing plan-bound maintained path.
- `SOURCE_FREEZE.json`: proposal, helper, source/dependency, review, pinned
  executable and actual index bindings. Prepared sources are unchanged.

Scoring would use the plan's fresh
`G:\Just_Peachy_S6D\20260913T195357Z\width_scores_v2` and
`R\angles\width_analysis_v2`. The future runner directory
`R\runner\width_score_queue_v1` is not created here. COMPLETE requires 3840 new
scores, 1920 exact original control cells, 5760 exact coverage/scene rows and
15 bound aggregate artifacts. It never claims native confirmation,
physical/GUI/CM5 efficacy or overall S6D completion.

Proposed bounds: 14400 s total, 1800 s without a newly committed score, 45 s
heartbeat staleness and 45 s cooperative STOP grace. These are conservative
proposals, not measured performance. Root must review aggregation allowance:
bootstrap/final validation can remain live without advancing scientific
progress. Final validation emits throttled heartbeats without fabricated
increments. No physical restoration predicate is invented for an offline job.

## Reproduce preparation without scoring

Choose a fresh output suffix; existing artifacts are never overwritten. The
completed V1 command is documented for reproducibility, not a request to rerun.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py -B "$sim\scripts\s6d_score_queue_prepare_v1.py" --output "$r\runner\width_score_queue_preparation_v1" --width-queue "$r\runner\width_queue_v1\QUEUE.json" --adapter-plan "$r\angles\width_scorer_plan_v2\ADAPTER_PLAN.json" --protocol-source "$r\angles\width_score_protocol_review_v1\source_epoch\s6d_width_score_protocol_v1.py" --runner "$r\runner\source_epoch_ready_v3\s6d_runner_v1.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" -B "%SIM%\scripts\s6d_score_queue_prepare_v1.py" --output "%R%\runner\width_score_queue_preparation_v1" --width-queue "%R%\runner\width_queue_v1\QUEUE.json" --adapter-plan "%R%\angles\width_scorer_plan_v2\ADAPTER_PLAN.json" --protocol-source "%R%\angles\width_score_protocol_review_v1\source_epoch\s6d_width_score_protocol_v1.py" --runner "%R%\runner\source_epoch_ready_v3\s6d_runner_v1.py"
```

No polling is installed. Missing/noncomplete data cannot become successful empty
scores. This epoch requires the accepted root width closure; absent/different
indices fail without creating production authority.

## Root-only finalization after review

Follow `ROOT_ADMISSION_RECIPE.json` in order. Root creates a fresh final
authorization after reviewing matrix, source closure, index and timing. Required
fields include the actual ordered index binding, plan/wrapper hashes, run/job
IDs and root owner IDs. Job ID: `OPERATIONAL_WIDTH_SCORE_ALL5760_V1`.

Root creates the final queue using `s6d_approved_job_queue_v1`, adds the actual
authorization binding to `source_bindings`, fills its SHA256 in the completion
predicate, and retains actual index binding and result predicates. Root computes
`runner.digest(job)` (SHA256 of sorted compact JSON), hashes final queue bytes,
then creates a separate `s6d_queue_approval_v1` with those exact hashes. Proposal
schemas/null hashes must not be passed as approved input. Do not edit the
completed upstream queue or relax source closure, storage floors, deadline or
fresh output requirements.

Only after root writes and reviews actual files, validate with the commands
below. The scorer script stays argv[1], without inserting `-B` in the queue;
the queue supplies PYTHONDONTWRITEBYTECODE.

PowerShell validation after root finalization:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
$scoreRun = "$r\runner\width_score_queue_v1"
$queueHash = (Get-FileHash -LiteralPath "$scoreRun\QUEUE.json" -Algorithm SHA256).Hash.ToLowerInvariant()
$approvalHash = (Get-FileHash -LiteralPath "$scoreRun\APPROVAL.json" -Algorithm SHA256).Hash.ToLowerInvariant()
& $py -B "$r\runner\source_epoch_ready_v3\s6d_runner_v1.py" --queue "$scoreRun\QUEUE.json" --approval "$scoreRun\APPROVAL.json" --queue-sha256 $queueHash --approval-sha256 $approvalHash --state-dir "$scoreRun\state" --validate-only
```

Anaconda Prompt / CMD validation after root finalization (replace the two
placeholders with the root-reviewed final byte hashes):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
set "SCORE_RUN=%R%\runner\width_score_queue_v1"
set "QUEUE_SHA=ROOT_REVIEWED_FINAL_QUEUE_SHA256"
set "APPROVAL_SHA=ROOT_REVIEWED_FINAL_APPROVAL_SHA256"
"%PY%" -B "%R%\runner\source_epoch_ready_v3\s6d_runner_v1.py" --queue "%SCORE_RUN%\QUEUE.json" --approval "%SCORE_RUN%\APPROVAL.json" --queue-sha256 "%QUEUE_SHA%" --approval-sha256 "%APPROVAL_SHA%" --state-dir "%SCORE_RUN%\state" --validate-only
```

Only root can launch after accepting validation: use the identical command with
`--validate-only` replaced by `--keep-awake`. Never call the scorer wrapper
directly or create an unattended retry. The runner continues to enforce
C>=50/G>=75 GiB, total new payload <=40 GiB, campaign deadline and exact owned
STOP identity. Review scientific scores, protocol completion and supervisor
closure separately.

