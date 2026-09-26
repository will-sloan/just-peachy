# Stopped V3 transport and complete-journal review

Purpose: `review_application_transport_v3.py` independently joins closed V3
application transport evidence and reconstructs its native event-envelope census.
V1/V2 code and qualifications remain unchanged. This internal reader has no production
acceptance CLI: a future full-panel reviewer must reconstruct the qualified V3
plan and all expected cells before passing expectations to `review_cell`.

Inputs: a stopped cell directory, independently reconstructed allowlisted payload
and plan digest, exact coordinator identity, code/interpreter bindings, coordinator
command and supervision path. It requires the fixed
`paced_application_runner_v3.py` script even when the preserved V1 runner also
appears in the dependency list. It checks INPUT/PERMIT/LEASE/CHILD_RESULT/LIFETIME,
application PREPARED/RESULT, COLLECTED and PARENT_CLOSURE joins; normal resumed exit,
private desktop, placement and exact observed-member exit; recorded slot census,
allowance, and the matching release. It never launches, signals or stops a process.

The native review joins ENGINE_CLOSURE's job/engine and direct session location
under `application/data/sessions`. It rereads native log segments and terminal
receipts using the qualified bounded strict reader, requires the whole sequence
including source start and completion, and reconstructs the entire expected
NATIVE_JOURNAL_ENVELOPE.json. A rebound but truncated journal, altered summary,
foreign session/cell/job or changed collected binding is rejected. It verifies
all evidence hashes again before returning. Raw transcript content stays private
and is not included in the returned count/hash metadata.

The V3 reader additionally requires the new child/cell/collection statuses and
exact preparation/collection delivery policy. It reparses the original binary
trace using the qualified application_delivery reader, binds the two source
classes to the planned source receipt, and reconstructs the entire expected
SOURCE_DELIVERY_ENVELOPE.json. The child's stored join and the parent's saved
summary must match that reconstruction. Rebinding altered summaries, partial or
changed traces, foreign capture paths, synthetic-capture flags, wrong origins or
old variants cannot satisfy collection review. It checks hashes again before
returning. The independent call does not invoke the runner's envelope writer and
never modifies the stopped run. Scheduling/append overhead is never subtracted.

`delivery_review_fixtures.py` is test support only. Its fabricated append times,
source facts and owner facts have no production admission. It builds bounded
binary fixtures without opening audio or importing/running an application. Its
rewrite helpers operate only on new probe fixtures and must never be used on
campaign evidence. Additional tests mutate envelope values even after rebinding,
truncate traces, swap capture pointers, change source origins or substitute an old
cell/policy. The positive join preserves every acceptance limitation.

Output: an in-memory `PASS_V3_APPLICATION_TRANSPORT_NATIVE_AND_DELIVERY_JOINS_ONLY`
record with transport and native/delivery bindings, current exact-process exit results,
recorded lifetime limitations and zero integrated N4 acceptance. Native payload
semantics, raw lexical correctness, naming, display content, source-to-widget
latency, source/worker/archive closure, full controlled resources and population
selection remain separate reviews. Only the last lease is retained; continuous
lease freshness and complete unsampled process history cannot be reconstructed.

The guarded probe runs on CPU14 alongside the admitted D1 component worker, holds
the helper lock, verifies exact D1 ownership and all protected bindings before and
after, and enforces existing space/allowance/deadline limits. Its 18 tests use inert
transport bytes and synthetic event journals; no fixture script/executable runs.
They preserve the earlier transport/lease/lifetime/slot failure tests and add older-runner
substitution rejection, independently reconstructed envelope checks and truncated
native-log rejection even after rebinding. Seven saved native Job Object fixtures
are reread, with current exact owner-exit checks (two normal, five refused). No new
application, GUI, source, model, device, playback or Pi operation occurs. Actual
production application/panel review remains unexecuted.

The private output contains ADMISSION.json, snapshots of these five new files,
tests.txt, synthetic review/classification records and RESULT.json or FAILED.json.
Every attempt needs a fresh directory. Keep these private fixtures out of Git.
Do not run development probes during controlled application measurements.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_transport_review_v3.py" --output "$jpLocal\n4\application-transport-v3-review-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_transport_review_v3.py" --output "%JP_LOCAL%\n4\application-transport-v3-review-probe-v1"
```

API for the independently qualified future full-panel reviewer:

```python
from review_application_transport_v3 import review_cell
result = review_cell(cell_directory, payload=reconstructed_payload,
    plan_sha256=reconstructed_plan_digest, coordinator=bound_run_owner,
    code=qualified_runner_code, executable=qualified_interpreter_binding,
    coordinator_argv=bound_run_command, state=bound_supervision_directory)
```

The caller supplies actual verified bindings, not these descriptive placeholders.
This API checks one cell and must not establish its own expected population from
whatever receipts happen to be present. Do not modify qualified source; repairs
require preserved failure evidence and a fresh version with relevant retests.

The guarded probe also preserves PROBE_OWNER.json and exact source snapshots before dependency admission. It uses CPU14 BelowNormal, one math thread, GPU off, the helper lock, a 720-second/8-MiB guard, C50/G75-GiB floors and the shared 50-GiB allowance including 6-GiB reserve. It is phase-specific to healthy D1; re-observe owners before a fresh attempt. No production panel is reviewed by the probe.
