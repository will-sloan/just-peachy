# S6A design registry and CM5 resource ledger

Purpose: build the complete 60-seed plus eight-new idea registry, a prospective
30-profile S6B plan, local model/storage resource ledger, source register, and
read-only Revision 14 workbook context receipt. This script does not perform
inference, hardware playback, downloads, installation, target deployment or S6B.

Inputs: the S6 V2 pack, its exact baseline/asset bindings, current local model
file metadata, and optional XVF_Measurement_V14.docx. Outputs live exclusively
under the chosen report's design directory. The original workbook and older
evidence stay unchanged. Registry entries remain proposals; structural
validation does not certify implementation or measured gains.

Use the existing Anaconda interpreter. No environment activation is required.
The script is standard-library-only. Re-running refreshes these derived design
files, so finalize the build receipt again after deliberately adding evidence
links. Keep active inference and design writers in separate directories.

PowerShell:

```powershell
$s6Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6Report = Join-Path $s6Sim 'reports\S6A\20260909T202250Z'
& 'C:\Users\amiri\anaconda3\python.exe' "$s6Sim\scripts\s6a_design.py" --report $s6Report
```

Anaconda Prompt or Command Prompt:

```bat
set "S6SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6REPORT=%S6SIM%\reports\S6A\20260909T202250Z"
"C:\Users\amiri\anaconda3\python.exe" "%S6SIM%\scripts\s6a_design.py" --report "%S6REPORT%"
```

Optional arguments: --pack "absolute extracted pack path" and
--workbook "absolute Word path". A missing workbook is reported without blocking
the current prompt's scope. Do not run historic setup/export commands merely
because source documentation is referenced.

The outputs are IDEA_REGISTRY_EXTENDED.json, IDEA_REGISTRY_SUMMARY.csv,
S6B_JOINT_PLAN.json, S6B_JOINT_TRIAL_PLAN.md, TARGET_RESOURCE_LEDGER.json/.md,
TECHNICAL_SOURCES.md, WORKBOOK_CONTEXT_RECEIPT.json and DESIGN_BUILD_RECEIPT.json.
Reviewers separately add measured-result bindings and skeptical review in this
directory. The builder never labels these proposed S6B profiles as executed.

Validation checks exactly 60 distinct preserved seed IDs, all eight distinct
new IDs, and 30 planned profiles. Exact API support, feature-cache mutation and
causality are established by the S6A component/cue tests, not by this catalog.
The resource ledger distinguishes local disk bytes and analytic buffer sizes
from separately measured desktop resident/private memory and untested CM5 performance.

The builder now attaches available component/API/frontend/profile, cue, baseline,
probe, native cache-mutation, invocation-boundary resume guards, reference-score,
and paced runtime receipts by hash. The current API authority is V2; superseded
pre-V2 API checks are not attached as current evidence. The resume-guard receipt
establishes uncached byte checking before dispatch, with unchanged dependencies
required throughout execution. The cache
receipt proves declared prospective identity rejection in actual completed-job
reuse; it does not establish minimal feature-DAG invalidation or changed graph
execution. Completed baseline/probe results are
attached only when their own status says complete; partial receipt bindings
remain labeled by source status and never become completed claims. The actual
P1X0/P1X1 settings are bound as prospective recipe R1, not an optimum. Runtime
V1 library-default observations remain separately identified from a controlled
final runtime experiment. The readable resource ledger summarizes actual
controlled V2 USS/RSS/private-commit/thread/write observations, with V1 retained
and the app-revision confound disclosed. Re-run after final evidence is ready to refresh these
attachments and the build receipt. No result file outside design is modified.
When all reference outputs are complete, the builder verifies the bound compact
reference and short-turn tables and derives matched R5/R1 cpWER error counts and
subsecond known-label coverage. These observed tradeoffs inform the plan without
equating known labels with correct identity or selecting a production tracker.
The frozen panel's source-based counts are derived separately: only two
subsecond utterances occur per tap in the 36-scene panel, versus 40 in the full
complete-reference study. Repeating profiles does not increase that sample.
The resource ledger labels logged model-phase times and their omitted wrapper,
gate, tracking, advisory/reset, formatting and I/O work; it does not call the
phase sum complete pipeline compute or calibrated latency.

When both final720 receipts are complete, the builder independently rehashes
all720 score JSON files, verifies unique profile/scene/tap coverage, population
counts, pooled word/cpWER counts, factorial arithmetic and ASR tail/drain cost
identities. INDEPENDENT_FINAL_REVIEW.json records these checks and adverse
outcomes; no metric engine or neural model is rerun. The plan/ledger carry the
complete observed panel rows, short-label coverage and actual child-wall context
while keeping S6B profiles prospective.

The exact component map, parameter binding and plumbing receipt versions used
by design are preserved under design/component_inputs with an origin/hash index.
This avoids a circular rewrite when the final component audit later links the
completed design. Current report-root component maps remain the human-facing
authority; the immutable copies retain historical nested-binding context.

New design consequences explicitly record the installed PalabraAI ReDimNet2-B2
frontend, dispatch-block RMS gate, cadence versus observation freshness, stable
wrong-direction failure, and the inactive provisional-merge path when a 1s
embedding immediately satisfies a 1s commitment threshold. Current 64-record
revision state remains distinct from proposed larger bounded queues.

Each of the 30 planned B rows now includes concrete numeric native profile
settings, exact input/gain preparation, and separately named additional policy
extensions when needed. A non-null extension is explicitly unimplemented and
must pass its effect tests before execution; running only its native foundation
does not execute that candidate. Native CLI syntax is recorded for the later B
orchestrator, but this design builder never launches those commands or B work.
Add --validate-native-plans to either build command to validate all 29 native
foundations (B00 uses unchanged historical B0) through the installed actual
ResearchProfile parser. PLANNED_NATIVE_SCHEMA_VALIDATION.json binds their exact
profile hashes and parser. This imports configuration code only, runs no
inference, and does not implement or execute the separate future extensions.

Add --review-probes using the same existing environment to audit all ten frozen
profile contrasts and replay at most 12 existing, hash-verified ReDim vector
caches through voice_time and reliability_adaptive with cues disabled.
PROBE_COMPARISON_AUDIT.json/.md retain exact field differences, equivalence
counts and interpretation limits; no audio or new inference is used, and no
vectors are copied to reports. This explicitly separates segmentation bundles,
cadence/RMS coupling, the factorial tracking-plus-endpoint route, cached tracker
equivalence and actual concurrent first-label display behavior. This optional
check requires existing NumPy. It does not launch or rerun the neural panel.

To reproduce the independent EOF accounting review, add --review-runtime.
This executes the current application's real ASR loop using a fake decoder
and a 1,707-sample in-memory journal. No models or hardware are opened. It
requires the existing environment's NumPy/SciPy imports and writes
design/INDEPENDENT_EOF_REVIEW.json. It checks exact input delivery, charged
107-sample tail and final drain, retained final text, and synthetic-padding
disclosure. It also runs an actual ResearchTracker fixture with synthetic
orthogonal 192-vectors: 0.5s windows permit a provisional merge/revision, whereas
1s windows immediately commit at a 1s evidence threshold and cannot reconcile
through that path. INDEPENDENT_TRACKING_DURATION_REVIEW.json records the
disproof and code binding without storing vectors. Neither fixture measures
recognition quality, correct real identities, GUI revision or calibrated latency.

PowerShell (after setting the same variables above):

    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s6Sim\scripts\s6a_design.py" --report $s6Report --review-runtime

Anaconda Prompt / Command Prompt:

    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%S6SIM%\scripts\s6a_design.py" --report "%S6REPORT%" --review-runtime
