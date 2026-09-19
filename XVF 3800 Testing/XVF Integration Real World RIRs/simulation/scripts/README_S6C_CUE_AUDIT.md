# S6C physical cue quality audit

`s6c_cue_audit.py` reads all240 preserved physical telemetry traces and produces
new descriptive cue-quality tables. It never opens hardware, calls a model,
modifies telemetry or changes a predictor. The physical trace is the sampling
unit and is counted once even though O0 and O1 share it.

## Inputs

The source authorities are the completed S6A `CUE_DELIVERY_INDEX.json` and
`CUE_FOUNDATION.json`, including their exact raw telemetry, capture metadata,
case-result and sanitized-delivery hashes. The canonical240-scene manifest is
the exact one bound by the preserved S6B epoch2 manifest. Original raw telemetry
is normalized with the existing S4 receipt/geometry helpers, which are bound in
the new audit plan. This helper imports only utility functions from the frozen
enrollment helper; no enrollment/model function is called.

Physical intervals split at actual packet arrivals, the independent250ms field
expiry and existing callback-quantized estimated activity boundaries. No future
interpolation, angle fitting or shift fitting is used. Raw/focused/scanning
directions use their existing same-index positive fresh-energy gates; selected
processed direction uses its documented finite/no-speech indication. Fields
are asynchronous. Selected-processed beam identity/energy is not manufactured.

## Measurements and denominators

For all six fields, retain total, angle-only and usable seconds for whole
capture, sole-person estimated activity, multiple-person activity, activity gaps
and all11 source-empty controls. Report receipt ages, native-field statistics,
measured/positive energy support and selected/raw/focused disagreement. Two
positive beam energies do not establish two independent speakers.
Music-control and digital-silence-control scenes also have separate whole-scene
denominators; these include their leading/trailing silence and are not asserted
to be exact music-active seconds.

Angles remain linear0..180 degrees:0 and180 are opposite endpoints. Per-turn
means/spreads use exactly one active source interval. Same/different reference
person turn-pair comparisons keep the nominal geometry difference, since the
same person can change seats. Source identities and manual geometry appear only
in evaluator outputs; they never enable a production mechanism. Manual±5deg
intervals are source uncertainty, not verified XVF accuracy. Stable wrong
directions can have small spread and large nominal error simultaneously.
A predetermined descriptive flag uses spread at most10deg and mean absolute
nominal error at least35deg. This flag is evaluator-only, not a sensor gate.

A fixed descriptive selected-angle change detector requires35deg difference,
25deg within-proposal consistency and0.75s sustained fresh support. Invalid
receipt periods break persistence. It does not receive reference labels.
Reference comparisons separately count local different-person transitions and
local nominal-position changes of at least35deg, with at most2s between eligible
sole-person states. One-to-one matches require a causal0..1s detection lag.
Longer-gap transitions are excluded explicitly. These are narrow local-change
diagnostics, not full diarization recall or optimized deployment thresholds.

Host receipt/source-callback alignment is observable; actual DSP observation
timestamps are not exposed. The original sanitized rows have no source span.
Freshly redelivered old device content therefore cannot be proven fresh using
these recordings. Repeated numeric values are not evidence of independent DSP
updates or of a stale device. Actual output-tap model-window association and v3
decision contributions are separate later analyses with their own receipts.

## Outputs

Under `simulation/reports/S6C/20260910T123540Z/cue_audit_v1`:

- `PHYSICAL_CUE_AUDIT_PLAN.json`: immutable code/source/policy authority before
  the new summaries.
- `cases/<case>.json`: per-field/population duration, energy, receipt, source-turn
  stability/disagreement and local-change evidence for one physical trace.
- `PHYSICAL_CUE_AUDIT.json`: complete240-case index and summed common-denominator
  summaries, with remaining feature/decision-chain scope explicitly unfinished.

Existing complete output is checked rather than overwritten. Unclosed partial
case output stops the helper for diagnosis; do not delete it to conceal a fault.
Use a separately named source/output revision for changed analysis definitions.

## PowerShell

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpAudit = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_cue_audit.py'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpAudit checks
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpAudit freeze
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpAudit run
```

## Anaconda Prompt or CMD

Use the installed environment directly, with no new dependency installation:
The helper loads this environment's NumPy before importing the old recorder
normalizer, whose dependency-directory precedence differs from this Python ABI.

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
set "JP_AUDIT=%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_cue_audit.py"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_AUDIT%" checks
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_AUDIT%" freeze
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_AUDIT%" run
```
