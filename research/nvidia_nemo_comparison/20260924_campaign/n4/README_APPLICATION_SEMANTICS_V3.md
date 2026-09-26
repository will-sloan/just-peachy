# V3 application caption, timing and heading review

Purpose: `review_application_semantics_v3.py` explicitly composes the qualified
delivery-aware V3 cell with native caption/widget consistency, the fixed display
roster, recorded row timing, applied GUI headings and evaluator-only conditional
name diagnostics. It preserves existing pure parsers and scoring arithmetic.
Earlier qualified files are unchanged. Its copied composition functions have
distinct V3 input/output status checks; no production API is monkeypatched and
no V2 receipt is relabelled to make it pass.

Inputs are a stopped V3 cell folder and expectations reconstructed by an admitted
V3 plan/run reviewer: payload, plan digest, coordinator creation identity, runner
code bindings, interpreter, exact command and supervision path. Production callers
must first admit the entire run/population; these functions cannot do that alone.
The cell reader independently reconstructs native and source-delivery envelopes
before semantic parsing. Every reused snapshot, native log, viewport log and
roster must retain the same content binding across readers. Roster order remains
baseline display-name order or N2 gallery document order as appropriate. Manual
corrections and optional text assistance cannot enter the primary caption check.

`review_content` returns `PASS_V3_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY`.
`review_timing` adds `PASS_V3_APPLICATION_RECORDED_ROW_TIMING_ONLY` and preserves
raw signed source-window intervals, missing observations and ambiguous native
predecessors. `review_labels` adds `PASS_V3_APPLICATION_RECORDED_GUI_LABELS_ONLY`:
active/history panes remain separate; forced, suppressed, anonymous, Unknown,
unrecognized and ambiguous headings remain distinct. Names do not become truth.
Delivery trace presence does not prove deadlines or physical screen latency.

`load_reference_context` rebuilds the already accepted 480-job evaluator context
using the qualified V3 application-context binding. Source, catalog and runtime
bindings must equal the older qualified context before this migration. The new
prestart context copied its gallery preparation manifest to a new path; both
manifests must verify and have identical SHA-256 and byte count before the
evaluator may use the new qualified path. Changed gallery content is rejected.
It preserves the original accepted N2 truth, scoring, audio-manifest and disjoint
E provenance inputs. The original reference receipt remains immutable. The new
context is `NEVER_PASS_TO_RUNTIME`; neither code nor tests send truth to an
application. `score_cell` joins a V3 observed heading result to this context and
calls the unchanged conditional naming arithmetic. All-Unknown and constant-name
controls preserve the same observed visibility opportunities. Estimated activity
support is not exact word identity. Outside the available roster also includes
intended members with missing enrollment, so it does not mean genuine outsider.

Outputs are private dictionaries for the caller to persist under its resource
guard. They include bindings and explicit unavailable/false acceptance fields.
No exact word naming accuracy, continuous wrong-name exposure, acquisition time,
returning-person consistency, fragmentation, deadline acceptance, controlled
resource tier, continuity, stop/restart, full-panel acceptance or N4 acceptance is
established by this reader. Full-panel semantic aggregation still needs explicit
V3 integration. These wrappers open no application, microphone, audio source,
model, device or Pi. They hash gallery vector files without loading the arrays.
Private transcripts, identities, profiles and full diagnostic results stay out
of GitHub. Only code, instructions and small redacted qualification receipts ship.

`test_application_semantics_v3.py` constructs fresh synthetic V3 cells, reusing
the actual pure span/casing methods and copied historical terminal metadata.
Its source append timestamps, process ownership and GUI geometry are fabricated.
The tests are development fixtures, never an actual runtime or production-plan
admission. Twenty cases cover both roster loader orders, malformed/changed
rosters, assisted/edited text, native/widget corruption, mismatched context,
cross-reader mutation, trace tampering, rejection of old heading/reference
receipts, signed timing/missing finals, the complete evaluator population, and
the composed content/timing/heading/name-diagnostic chain. Migration tests also
reject changed gallery bytes and an incorrect prior context binding.

Attempt v1 stopped before tests because its initial migration required identical
manifest paths. Inspection verified that only the gallery preparation path had
changed; both files were 16,725 bytes with the same SHA-256. V2 allows this exact
content-preserving relocation and records both old and new inputs. The failed
attempt, owner, admission and four source snapshots remain preserved.

Attempt v2 passed 18 of 20 checks; two baseline fixtures stopped during setup
because switching their synthetic backend left the fabricated capture bound to
the original contract. V3 updates only each new fixture's capture fingerprint
before review. Production capture validation is unchanged; v2 evidence remains.

`probe_application_semantics_v3.py` pins its helper to CPU14/BelowNormal, one math
thread, GPU disabled. It uses the existing writer lock, 12-minute/8-MiB probe
bound, private allowance including reserve and C:/G: free-space floors. It checks
live D1 exact owners, heartbeat and protected code before/after and does not
start a second numerical worker. Every fresh attempt records its owner and four
source snapshots before fragile prerequisites. Outputs are PROBE_OWNER,
ADMISSION, REFERENCE_INPUTS, tests.txt and RESULT, or preserved FAILED evidence.
Run outside exclusive resource tests; never overwrite or delete a prior attempt.

PowerShell (choose a fresh output name if this attempt already exists):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_semantics_v3.py" --output "$jpLocal\n4\application-semantics-v3-probe-v3"
```

Command Prompt or Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_semantics_v3.py" --output "%JP_LOCAL%\n4\application-semantics-v3-probe-v3"
```

Internal API, only after independent V3 production-plan/run admission:

```python
from review_application_semantics_v3 import review_labels, load_reference_context, score_cell
observed = review_labels(stopped_cell, checkpoint=bounded_guard, **admitted_expectations)
references = load_reference_context(checkpoint=bounded_guard)
diagnostics = score_cell(references, observed, admitted_expectations['payload'], checkpoint=bounded_guard)
```

The example identifiers represent independently verified inputs, not user-supplied
claims. A passing probe does not authorize or certify a new source-paced run.
