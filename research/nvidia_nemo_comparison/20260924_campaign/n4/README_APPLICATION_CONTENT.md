# Application evidence and caption content composition

Purpose: `review_application_content.py` composes the qualified V2 cell review
with the primary native-caption/recorded-widget checker. It first reconstructs
the fixed qualified application source context, then checks cell ownership,
transport, native envelope, source/consumer closure, resource observations and
viewport evidence through the earlier readers. The prepared gallery and final
Controller snapshot must contain the same display roster in the order used by
the actual loader. N2 preserves document profile order; the baseline sorts by
display name. Baseline manifest, metadata and vector file bindings are rechecked
without loading arrays or a model. Available, intended and unavailable roster
counts remain separate. No personal profiles are searched or enrolled.

Inputs: one stopped V2 cell directory and the exact `payload`, `plan_sha256`,
`coordinator`, child `code`, `executable`, `coordinator_argv` and `state` inputs
derived from an independently admitted complete V2 panel plan/run. The API does
not accept a caller-supplied names list. The fixed display roster is derived from
the admitted gallery, matched to both snapshot people fields and passed to the
widget checker. Mode must be primary `open_with_names`, with no strict filter,
selected subset, text assistance, manual edits or optional corrected text.

Output: a private in-memory
`PASS_V2_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY` result containing the
cell, roster and content reviews with matching evidence bindings. It establishes
consistency of those recorded facts. It does not establish recognition/naming
accuracy, latency, continuous exposure, resource tiers, full panel coverage,
continuity, stop/restart or N4 acceptance. Missing visibility and ambiguous
native predecessors remain explicit. A unique text match is still not proof
of the precise consumed native event. All integrated acceptance counts remain
zero. Nested reader flags retain their original narrower scope; the top-level
join flags describe only this composition's added checks.

This reader opens no application, window, audio source, device or Pi. It uses
the already qualified complete-journal derivative and does not edit earlier
bound reviewers. Callers must provide bounded checkpoints and output limits.
Inputs are limited to 256 roster entries, 8 MiB for a gallery document, 1 MiB
for preparation/manifest records and 64 KiB per metadata/vector binding, plus
the existing native/viewport/cell limits. Vector bytes are hashed only. Private
transcripts, headings, rosters and gallery contents must not enter public Git.

The guarded probe runs on CPU14/BelowNormal with one math thread, no GPU, the
helper lock, a 12-minute bound and the campaign disk/private allowance. Exact
D1 owners, heartbeats and protected code are checked before and after. Each
fresh attempt records its owner and four source snapshots before prerequisites;
failed attempts are preserved. Twelve tests compose the actual readers with
synthetic process, clock, journal and viewport facts. They call unchanged pure
span/casing methods and reuse historical closure metadata only inside fresh
fixtures. Tests cover both loader orders, changed names/order, assistance,
manual corrections, corrupt native/widget text, foreign context, changed
evidence, roster denominators and baseline metadata. No positive fixture is a
new real application run or measured latency result.

Attempt v1 failed during fixture construction because the reused event emitter
stamped its old session ID while the pure span state used the enclosing cell's
session ID. V2 stamps the matching ID before state consumption. The original
failed attempt and snapshots remain preserved; production validation is unchanged.

Run outside exclusive paced measurements and choose a fresh output directory.
PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_content.py" --output "$jpLocal\n4\application-content-probe-v2"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_content.py" --output "%JP_LOCAL%\n4\application-content-probe-v2"
```

Internal API after independent panel-plan/run admission:

```python
from review_application_content import review_cell
private_review = review_cell(stopped_cell_folder,
    checkpoint=bounded_evaluator_guard, **verified_cell_expectations)
```

The identifiers stand for independently verified inputs. The older qualified
panel reviewer still uses its original narrower V2 cell review; this composition
must be invoked explicitly by a future separately qualified panel wrapper.
