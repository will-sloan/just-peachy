# S6C actual feature and cue-decision diagnostics

`s6c_cue_decisions_v2.py` reads the sealed, real S6B R0 embeddings and completed
S6C epoch1 N00 policy predictions. It makes no model calls, reruns no policy,
changes no predictor and opens no hardware. This is an evaluator, not an
alternative tracker implementation.

## Version lineage

V1 completed the480-feature audit and7392 actual action summaries, but its
strict matcher omitted the required delivery-route toggle and admitted zero
contrasts. V1 remains unchanged. V2 reuses the exact bound
`cue_decisions_v1/R0_FEATURE_CUE_AUDIT.json` and original per-feature files; it
re-reads actual predictions only to add correct matched contrasts and chains.
The first three config differences are exhaustively restricted to profile ID,
tracker cue-enable and XVF tracking delivery routing. This is a report-only
repair, not a change to predictions, upstream inference or decision policy.
The V2 plan binds the original code/README/action receipt and feature authority.
The inherited feature helper body is retained as source history but is not
exposed as a V2 command and is not run. V2 does not create a new feature bank.

## Inputs and source authority

The exact S6B local artifact index hash resolves the old execution, 480-input and
full native-receipt indexes. Every R0 receipt, evidence/vector binding, saved
reference-support and delivered telemetry file is checked before use. The
completed epoch1 index contains exactly66 candidates x56 challenge cases x2
taps. Actual prediction hashes, epoch/config identity, feature IDs, source spans
and available times are checked. The new plan freezes these authorities and the
analysis code/README before summaries are produced.

## Feature measurements

All480 output views retain every actual0.5s R0 embedding. The physical capture
denominator remains240, shared between O0/O1. Existing estimated source-with-RIR
support is mapped with the saved output offset once; the50ms RIR convention is
already included. No new alignment is fitted. A reference-qualified window has
at least50% estimated activity from exactly one metadata person and no activity
from another. These are scorer-only labels, never runtime gates.

All within-case, disjoint waveform-window pairs are retained. Pairwise cosine
from actual normalized ReDim vectors defines a fixed descriptive ambiguity band
0.20..0.65. Separate same/different-person and shared-original-clip strata retain
missing cue pairs in their denominators. Absolute angle differences use the
linear0..180 coordinate. Disjoint windows do not imply independent utterances or
statistical trials. The band is not a calibrated posterior or a cloned tracker
uncertainty state.

A delivered-cue prerequisite uses the latest actually delivered row at embedding
availability: finite valid linear angle, host receipt age at most250ms and
recorded reliability at least0.2. DSP source age is unknown. This is explicitly
not the whole tracker gate: the actual logged cue qualification is authoritative
in the action analysis.

## Actual decision chains and matched contrasts

The action pass reads all7392 existing v3 outputs. It counts actual audio/cue
rejections, logged joint candidate comparisons, nonzero logged joint cue-score contributions,
borderline existing-track selections, lifecycle/evidence/prototype lineage and
display events. It does not count parser support as activation. The old_voice_gate control
logs eligibility/action but no numeric candidate breakdown; zero logged joint
contributions is not proof of zero internal spatial ranking for that control.

Only profiles exactly equal after removing their display profile ID and toggling
`tracker.cues_enabled` and changing the explicit delivery route `xvf.mode`
from `none` to `tracking_only` are cue-matched. No other config change is allowed. All eligible identical parent IDs are
listed; the lexicographically first is the comparator. Null reassignment seeds
and nominal-geometry oracle diagnostics remain explicitly labelled. Raw ASR
words must be equal in each label-only matched pair.

For qualified disjoint observation pairs, compare their actual SAME/DIFFERENT/
UNKNOWN track relationships with scorer-only same-person truth. Track-number
renaming cannot change the result. WRONG-to-CORRECT and CORRECT-to-WRONG are
separate from resolving Unknown or losing a known correct association. These
overlapping all-pair counts are not cpWER, DER, independent trials or name
accuracy. They can include accumulated cue-state changes and do not establish a
single-packet causal effect.

For each contrast/tap/category, at most the first two deterministic examples
retain the received cue, actual acoustic admission, actual voice/cue/new/
unresolved scores and action, evidence/prototype lineage, and display events
explicitly referencing that evidence ID. No display link is guessed. N00 uses
identity mode none, so naming is unavailable here; actual-C gallery and native
gallery proofs cover that separate branch.

## Outputs

Under `simulation/reports/S6C/20260910T123540Z/cue_decisions_v2`:

- `CUE_DECISION_PLAN.json`: frozen code and input authority.
- Feature authority remains the original V1 receipt and files; V2 binds it
  explicitly and does not rewrite or duplicate the feature bank.
- `N00_ACTION_ROWS.json`: one row per real completed policy output.
- `N00_MATCHED_RELATION_ROWS.json`: per-case matched co-assignment diagnostics.
- `examples/*.json`: bounded helpful, harmful and Unknown transition chains.
- `N00_CUE_ACTION_AUDIT.json`: complete action index and compact summaries.

Completed outputs are not overwritten. If interrupted, preserve partial output
and diagnose before introducing a new explicitly versioned output namespace.

## PowerShell

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpAudit = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_cue_decisions_v2.py'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpAudit checks
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpAudit freeze
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpAudit decisions
```

## Anaconda Prompt or CMD

Use the existing native environment; no install or activation is necessary.

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
set "JP_AUDIT=%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_cue_decisions_v2.py"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_AUDIT%" checks
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_AUDIT%" freeze
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_AUDIT%" decisions
```
