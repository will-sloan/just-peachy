# S6B inference, cache and replay accounting

`s6b_inference_accounting.py` audits the full-confirmation admission arithmetic
and counts actual recorded native work separately from model-free replay. It
reads only compact receipts, indexes, process identities and metadata. It does
not import the application, open audio/models/vectors/event logs, run inference,
alter active code or stop any process.

## Inputs and arithmetic

Inputs are the authoritative epoch2 manifest and bound input/profile/challenge
metadata, `FULL_CONFIRMATION_ADMISSION.json`, its bound prior R0 full index,
the completed challenge native index, epoch2 native run/attempt receipts,
coordinator invocation metadata, and report-root prediction indexes.

The current admission is checked from actual scene/tap/index coverage:

-6 recipes x240 scenes x2 taps =2880 full native outputs.
-6 x44 x2 =528 prior challenge native outputs.
-R0 contributes392 additional prior full-bank extension outputs.
-The union contains920 reusable outputs, leaving1960 new native outputs.
-23 prior R0/historical profiles plus6 added profiles =29 full profiles,
  producing13920 requested predictions. That is not13920 neural runs.

The script verifies the exact recipe/scene/tap sets and compares every declared
total. It preserves the exact admitted JSON bytes in each timestamped audit
directory. Admission estimates remain prospective engineering estimates; no
count is silently promoted to completed work.

## Counting rules and cost interpretation

Completed native jobs are unique recipe/scene/tap logical identities. A physical
attempt is identified by job key, PID, process creation time and start timestamp.
The completed run receipt and its matching attempt receipt represent one
execution, not two. Distinct physical attempts for the same logical job are
reported explicitly. Missing or still-started work does not become a successful
model run. Both completed run and STARTED/FAILED/COMPLETE attempt receipts must
match the authoritative execution epoch digest before entering any totals.

Coordinator `COMPLETE_REUSED` rows are counted separately from newly completed
rows. Multiple invocation/index references to one receipt never create new
neural work. Closed invocations without completion receipts are flagged but not
automatically called model failures: the preserved execution fault ledger
documents status-I/O failures after successful audio completion. PID and process
creation time distinguish active ownership from recycled PIDs. No process is
modified.
Completed native receipts without a recorded fresh COMPLETE invocation row are
listed explicitly. A coordinator can lose its row after the worker durably
finishes; its later COMPLETE_REUSED row does not become a new model run. During
a live snapshot the inverse difference can also occur when more work completes
between initial receipt enumeration and later invocation-row inspection. Final
closed-worker accounting distinguishes preserved I/O losses from that timing.

`resident_bundle_load_count` is cumulative within each worker. The audit takes
the maximum observed value per PID+creation time and sums those maxima, never
the per-scene counters. A load occurring before any preserved receipt is not
observable and is not invented. Each worker's recipes and observed lifetime are
listed. Successful native operation events are summed once per completed job;
ASR dispatch counts are API observation records, not the hidden number of
Sherpa forward steps.

Inclusive native session wall time, full process CPU, source audio duration and
nested resident admission/check wall time are reported separately. Admission
is already inside full session wall time and must not be added a second time.
Concurrent lane model times are not summed into measured latency. Physical
attempt costs, including available incomplete/faulted records, remain separate
from unique successful job costs. Missing cost fields are counted explicitly.

Prediction indexes are deduplicated by profile/scene/tap and must agree on exact
output bindings within the authoritative epoch prediction namespace. Independently
materialized pilot-validation predictions outside that namespace are listed
separately; sharing a profile/scene/tap name does not make them the same file or
a campaign cache conflict. The audit reports unique indexed outputs, historical B00
reuse, actual-neural-feature-derived outputs, and duplicate cross-index
references. Those duplicate references are not measured replay cache-hit counts:
the replay script does not log every execution versus reuse separately. Active
unindexed prediction files are excluded. Historical B00 comes from S6A; component
smokes and future paced cells belong to their separately receipted scopes.

This accountant does not replace native artifact or prediction integrity
guards. It binds compact receipts/indexes without rereading their heavyweight
payloads. During active work it reports a bounded read-interval snapshot; more
files can complete after enumeration. Run again after all workers close for the
final accounting. This script does not claim model accuracy, final scoring
completion, a CM5 speed multiplier, RAM fit or deployment readiness.

## Outputs

Each execution creates `REPORT/inference_accounting/audit_<UTC>/` containing:

-`FULL_CONFIRMATION_ADMISSION_SNAPSHOT.json`: exact admitted source bytes.
-`INFERENCE_ACCOUNTING.json`: arithmetic, counts, missing jobs, costs, process
  load counters, invocation/fault classifications and inspected file bindings.
-`INFERENCE_ACCOUNTING.md`: compact human-readable findings.

`REPORT/inference_accounting/LATEST.json` points to the latest timestamped audit.
Prior audits remain intact. Atomic report writes use unique temporary names and
bounded Windows sharing-denial retries. No history is deleted or overwritten.
Live JSON snapshot reads also retry transient sharing denials for a bounded1s.
Mutable live coordinator rows may change after a snapshot; their recorded hash
describes the observed bytes, not an assertion that active status files remain
immutable. Final closed invocation evidence is stable.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py "$sim\scripts\s6b_inference_accounting.py" --test
& $py "$sim\scripts\s6b_inference_accounting.py" --report "$sim\reports\S6B\20260909T230840Z" --epoch epoch2
```

## Anaconda Prompt / Command Prompt

The existing EDGE environment supplies Python and psutil. No installation or
environment change is needed.

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6B_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6B_PY%" "%SIM%\scripts\s6b_inference_accounting.py" --test
"%S6B_PY%" "%SIM%\scripts\s6b_inference_accounting.py" --report "%SIM%\reports\S6B\20260909T230840Z" --epoch epoch2
```

Six model-free fixtures cover cumulative loads/PID reuse, the admission union,
run/attempt deduplication, distinct physical attempts and inclusive/nested cost
separation, plus foreign-epoch attempt rejection. They validate accounting logic,
not neural behavior.

The first live accounting attempt preserved the admission, then correctly
stopped when independent pilot-validation materializations were initially
combined with the primary prediction namespace. The namespace rule above was
made explicit before the successful accounting snapshot. No prediction,
inference or active runner was changed or repeated.
