# Stopped V2 transport and complete-journal review

Purpose: `review_application_transport_v2.py` independently joins closed V2
application transport evidence and reconstructs its native event-envelope census.
V1 code and qualifications remain unchanged. This internal reader has no production
acceptance CLI: a future full-panel reviewer must reconstruct the qualified V2
plan and all expected cells before passing expectations to `review_cell`.

Inputs: a stopped cell directory, independently reconstructed allowlisted payload
and plan digest, exact coordinator identity, code/interpreter bindings, coordinator
command and supervision path. It requires the fixed
`paced_application_runner_v2.py` script even when the preserved V1 runner also
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

Output: an in-memory `PASS_APPLICATION_TRANSPORT_AND_NATIVE_ENVELOPE_JOINS_ONLY`
record with transport and native bindings, current exact-process exit results,
recorded lifetime limitations and zero integrated N4 acceptance. Native payload
semantics, raw lexical correctness, naming, display content, source-to-widget
latency, source/worker/archive closure, full controlled resources and population
selection remain separate reviews. Only the last lease is retained; continuous
lease freshness and complete unsampled process history cannot be reconstructed.

The guarded probe runs on CPU14 alongside the admitted D1 component worker, holds
the helper lock, verifies exact D1 ownership and all protected bindings before and
after, and enforces existing space/allowance/deadline limits. Its 15 tests use inert
transport bytes and synthetic event journals; no fixture script/executable runs.
They preserve the earlier transport/lease/lifetime/slot failure tests and add V1
substitution rejection, independently reconstructed envelope checks and truncated
native-log rejection even after rebinding. Seven saved native Job Object fixtures
are reread, with current exact owner-exit checks (two normal, five refused). No new
application, GUI, source, model, device, playback or Pi operation occurs. Actual
production application/panel review remains unexecuted.

The private output contains ADMISSION.json, snapshots of these four new files,
tests.txt, synthetic review/classification records and RESULT.json or FAILED.json.
Every attempt needs a fresh directory. Keep these private fixtures out of Git.
Do not run development probes during controlled application measurements.

Attempt `application-transport-v2-review-probe-v1` failed before admission/tests
because the probe passed two filenames to a single-file loader. Its exact four
source files and failure receipt are preserved; the exited helper's identity was
not recorded before that failure. The corrected probe uses fresh attempt `v2`.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_transport_review_v2.py" --output "$jpLocal\n4\application-transport-v2-review-probe-v2"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_transport_review_v2.py" --output "%JP_LOCAL%\n4\application-transport-v2-review-probe-v2"
```

API for the independently qualified future full-panel reviewer:

```python
from review_application_transport_v2 import review_cell
result = review_cell(cell_directory, payload=reconstructed_payload,
    plan_sha256=reconstructed_plan_digest, coordinator=bound_run_owner,
    code=qualified_runner_code, executable=qualified_interpreter_binding,
    coordinator_argv=bound_run_command, state=bound_supervision_directory)
```

The caller supplies actual verified bindings, not these descriptive placeholders.
This API checks one cell and must not establish its own expected population from
whatever receipts happen to be present. Do not modify qualified source; repairs
require preserved failure evidence and a fresh version with relevant retests.
