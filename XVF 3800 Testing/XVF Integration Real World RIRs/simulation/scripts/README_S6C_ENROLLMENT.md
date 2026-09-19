# S6C native enrollment and C-only calibration

`s6c_enrollment.py` creates actual research speaker templates through the unchanged
`enrollment.enroll_wavs` and `speakers.ProfileStore.load()` in the preserved
S6B application snapshot. It then creates isolated explicit galleries and fits the
seven prospectively registered score/margin alternatives from C audio alone.
It does not run Q audio, train a model, access a private user gallery, download
data, or operate hardware.

The fixed run is `20260910T123540Z`. This helper is a separate source from the
completed `s6c_sources.py` material preparer; it does not replace its evidence.

## Inputs and exact application boundary

The required preparation authority is
`reports/S6C/20260910T123540Z/enrollment_inventory/v2/PREPARATION_RECEIPT.json`,
its bound ECQ manifest, coverage CSV and Q occurrence manifest. The independent
`SOURCE_MATERIAL_REVIEW_V1.json` must pass before the plan can be frozen. The
prepared E and C waveforms are whole mono16k FLOAT clips on G: with unity gain,
explicit estimated usable support and frozen source/checkpoint hashes. All E/C/Q
source, original/decoded hash, normalized text and native prompt intersections
must be empty. No Q file is embedded by this helper.

Application imports come exclusively from
`staging/s6c/20260910T123540Z/s6b_app/edge_speech_pipeline`, verified against the
intake snapshot. A fresh process rejects any pre-imported application. Explicit
existing ReDimNet2 and Pyannote asset paths/hashes come from the preserved S6B
epoch2 manifest. One lazy shared native `SpeakerModels` has one inner CPU thread.
Its constructor loads both graphs; this helper invokes ReDim embedding only.
No ASR, segmentation inference or live application code is used.

The frozen plan binds this helper/README, all preserved application Python files,
material and design authorities, both model assets and exact numerical library
versions. Changing a dependency after the plan is frozen causes rejection. Keep
the existing plan/evidence and investigate a new revision instead of overwriting.

## Frozen roster rules

Before any enrollment/calibration inference, metadata IDs are ordered separately
per corpus by SHA256 of `S6C_roster_seed_23:` plus the corpus-qualified ID.
Fixed A takes even zero-based indices; fixed B takes odd indices. Large cohort
takes indices modulo4 other than3, retaining planned withheld strangers.
The intended fixed rosters remain independent of Q appearance and model scores.
Each tier includes only actually available E templates, records missing people,
and retains every Q case in later scoring.

Three explicitly labeled simulated user setup conditions may use the scene cast:
all expected people; lexicographically first participant; and that selected
participant replaced by the first seeded absent person eligible at the tier.
Other true voices remain unselected in the wrong-selection condition. This is
explicit setup information and never an ordinary fixed-roster predictor input.
The source-empty fallback is the first four lexicographic fixed-A identities;
the canonical240 cases include11 source-empty controls. The exact S6B-bound
canonical scene manifest initializes the complete case grid before Q occurrences
are assigned, so those controls retain their setup-gallery rows. An unavailable roster is
an explicit `profiles: []` gallery, not a fabricated replacement voice. The
S6C application preserves anonymous labels and performs no name query for it.

Manifest `schema_version` is `edge-research-gallery.v1`. Only pseudonymous
`Research Person NNN` names, native profile IDs, backend identity and exact
metadata/NPY sibling bindings enter this predictor manifest. Corpus IDs, expected
cast, known/unknown roster membership and setup provenance are in the separate
scorer-only map. Byte-identical native metadata and vectors are copied to each
distinct tier/member roster root. The metadata's original `vector_path` remains
the canonical enrollment path; actual ProfileStore loads the admitted sibling.
Equivalent condition/case rosters share one immutable manifest. No private
default root is consulted.

## Enrollment and C scoring semantics

Each available5/15/30-second tier calls actual `enroll_wavs` on its original
nested whole-clip prefix. The duration is estimated unique usable source support,
not inference-window count. Native enrollment embeds up to2s windows on1s hops
with a minimum0.5s window, averages all returned normalized vectors, and
normalizes the centroid. Its native RMS and consistency checks remain active.
Overlapping enrollment windows do not become additional unique source seconds.

An exact waveform cache avoids repeated native graph calls for a window shared
by nested tiers. The key binds the entire frozen plan and float32 samples; every
hit verifies the exact keyed target path, then loads the same verified bytes and
checks shape. Actual native embedding calls,
cache hits and native enrollment aggregation counts are separately recorded.
No vector is substituted by metadata or a source identity label. An unreceipted
partial template/cache vector stops recovery and is retained for investigation.

C queries are nonoverlapping up-to2s windows from accepted C clips; a terminal
window is used only when at least0.5s remains. There is no padding, loop, crop
concatenation or source gain. The same native normalized embedding is scored
against vectors returned by the actual `ProfileStore.load()` in manifest name
order, using single-query float32
dot products and Python-float threshold/margin comparisons. Natural pauses
remain. This is a score calibration protocol, not a simulation of the complete
online identity-state accumulation or a claim of calibrated probabilities.

The reusable C embedding pool covers people available in at least one gallery.
For each fit, its matrix includes only C identities in that exact available
fixed roster/tier. Withheld strangers are absent from that condition's C queries.
Every nontrue template column is a legitimate known-person/wrong-template score.
No Q embedding, scene result or wrong stranger voice is used to fit a threshold.
The registered32-point score/margin grid minimizes wrong-known acceptance, then
maximizes correct acceptance, then chooses higher threshold/margin on ties.
Fewer than four eligible waveform queries retains the inherited thresholds with
`UNAVAILABLE_CALIBRATION`. Window, distinct clip, known person and missing-C
person counts are preserved; windows are not independent speaker trials.

The prepared material has37/30/28 people at5/15/30s. CMU18 and HiFi10 reach every
tier; CV9 reach5s and CV2 reach15s, with none at30s.28 people have30s of C and8
have smaller C material. Three HiFi E/C pairs use different chapters of the same
book; no Q book is reused. Recording sessions and undocumented transformed
aliases are not exhaustively established. These are research identities and
source domains, not user identity verification or future-training clearance.

## Outputs

Small authority/receipt outputs are under
`simulation/reports/S6C/20260910T123540Z/enrollment`:

- `ENROLLMENT_PLAN_V2.json`: authoritative immutable pre-inference rules, members
  and bindings; prior unexecuted plan1 is retained with explicit lineage.
- `templates/*.json` and `TEMPLATE_INDEX.json`: actual native enrollment receipts.
- `SCORER_GALLERY_MAP.json`: corpus identity/profile/name/condition/tier mapping;
  evaluator-only, never anonymous association input.
- `calibration/C110.json` through `C116.json` and `C_ONLY_CALIBRATION_INDEX.json`:
  exact per-roster C matrices, grid, selected parameters and coverage.
- `ENROLLMENT_COMPLETION.json`: source-bound completion and per-process costs.
- `EMBEDDING_CACHE_INDEX.json`: all immutable waveform invocation receipts,
  including any preserved completed cache entries across resumed processes.
- `workers/*.json`: owned process identity and function-body completion state;
  operating-system process exit is independently observed after the command.

The root report `RESEARCH_GALLERY_INDEX.json` resolves each condition/tier/case
to exactly one actual gallery manifest. Payload is isolated under
`G:/Just_Peachy_S6C/20260910T123540Z/enrollment`: native template roots, explicit
gallery roots, exact embedding cache and `calibration/C_WINDOW_EMBEDDINGS.json`.
The predictor sees gallery files; the scorer-only map and C matrices remain
offline analysis evidence. No earlier S6B artifact is modified.

## Run in PowerShell

Use the already installed project environment; no environment installation is
needed. `self-test` and `freeze` make no model calls. `run` performs the authorized
native E/C inference. `verify` checks completed output bindings with zero model
calls. Close a previous helper process before resuming the same command.

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpScript = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_enrollment.py'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpScript self-test
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpScript freeze
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpScript run
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpScript verify
```

## Run in Anaconda Prompt or CMD

This explicitly invokes the established environment's interpreter and does not
require activating a different Conda environment.

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
set "JP_SCRIPT=%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_enrollment.py"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_SCRIPT%" self-test
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_SCRIPT%" freeze
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_SCRIPT%" run
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_SCRIPT%" verify
```

Run/resume refuses code or asset changes, wrong-source/tier template checkpoints
(including ordered native source paths, backend, isolated root and native window
count), redirected vector cache bindings,
changed bytes even with old modification times, and unreceipted partial native
outputs. It verifies existing complete templates rather than reenrolling them.
The final verification does not imply GUI validation, hardware validation,
continuous runtime timing, Pi/CM5 feasibility or recognition accuracy.

The first pre-inference freeze rejected an incorrect assertion that all240 cases
had Q occurrences: Q777 spans229 cases and11 source-empty controls. No plan or
model result was created by that failed freeze. The originally reviewed helper
and README are preserved in `staging/s6c/20260910T123540Z/enrollment_builder_review_v1`;
`enrollment/PRE_INFERENCE_COVERAGE_REPAIR_LINEAGE_V1.json` resolves their old review
bindings. This preparation-only repair binds the full scene manifest and adds a
source-empty-grid fixture. Earlier review/check receipts remain unchanged.

The unexecuted plan1 and its reviewed helper/README are also preserved before a
second narrow repair: completed enrollment resume now rereads every original and
decoded source binding, as fresh execution already did. The resolver is
`enrollment/UNEXECUTED_PLAN1_RESUME_REPAIR_LINEAGE_V1.json`, and the exact prior
source snapshot is `staging/s6c/20260910T123540Z/enrollment_builder_review_v2`.
Authoritative plan2 changes no roster, native embedding or C scoring rule.
