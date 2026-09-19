# Actual C-vector gallery branch proof

`s6c_gallery_proof.py` sends existing real C ReDimNet2 vectors and their numerical
source-activity support through the frozen epoch1 v3 tracker/name scheduler. It
loads actual native ProfileStore galleries and preserves the original score,
margin, evidence duration and disjoint-observation requirements. This makes no
model calls, new templates, audio synthesis, downloads or hardware operations.

The four mechanism conditions keep a person's reference present, remove the same
person, provide a distractor-only gallery, and introduce a different real voice
after the primary person's evidence. They are deliberately constructed C-only
mechanism controls, not Q accuracy or native full-pipeline confirmation.

## Inputs and selection

The source is the completed `enrollment/ENROLLMENT_COMPLETION.json` and its bound
E/C material, actual template/gallery/scorer-map indexes and C window vectors.
The helper runs completed-source verification before reading those artifacts.
Application Python files are from the immutable S6C epoch1 snapshot and checked
against its execution manifest. It uses the original C088 O0 identity profile,
without any calibrated scalar or scheduler/tracker change.

Choose the lexicographically first fixed-A15s person and fixed-B15s person with
at least six full2s C windows having at least50% estimated numerical source
activity. Use the first six windows in source-ID/sample order. No cosine score
or branch outcome is used to choose them. The distractor-only condition uses an
existing15s singleton gallery excluding the primary person, ordered by member
ID, condition and case. No new profile vector or metadata file is created.

The complete event plan is saved before running any branch. Source spans refer
to the existing decoded C file, whose original and decoded hashes are retained
for each event. Whole numerical activity masks are intersected with the actual
window; no identity label becomes a clean-support mask. Waveform-derived RMS and
clipping are read from those exact samples.

## Interpretation limits

This is a scheduler feed with real cached vectors. The numeric source-activity
mask is not an actual Pyannote output. Clean single-source corpus windows carry
the existing mature evidence role and speech flag; they do not establish how
the live gate would behave. Sources are placed in a modeled sequential timeline
with1s between clips and availability at end+1ms. This is neither actual physical
timing nor a new simulated audio capture. Evidence coordinates and clip origins
remain explicit, and no extra unique duration is credited for repeated windows.

Every condition starts a fresh actual scheduler. The profile keeps score
0.5128856897354127, margin0.03, minimum unique evidence2s and two disjoint
observations. Actual names may be tentative, confirmed or unresolved. Failures
and wrong-name events are retained as observations; their absence is not a
general open-set error-rate estimate. The conflict condition may create another
anonymous track instead of exercising a same-track revocation; report what
actually happens. Nothing forces a reference identity onto a track.

No fabricated ASR transcript is supplied. Results are actual speaker/identity
events; full native Runtime ASR/name integration is a separate root-owned test.
Q accuracy, calibration generalization, continuous runtime timing and deployment
readiness are outside this proof.

## Outputs

Outputs are under
`simulation/reports/S6C/20260910T123540Z/enrollment/gallery_branch_proof_v1`:

- `BRANCH_PLAN.json`: source-bound event/condition plan before branch execution.
- Four condition JSONs: actual scheduler events, naming/track state, gallery
  load receipt, per-query source bindings and explicit correct/wrong/unresolved
  counts. Corpus identities are scorer-only provenance outside predictor events.
- `GALLERY_BRANCH_PROOF.json`: compact outcome counts and exact result bindings.

Existing results are verified rather than overwritten. A change requires a
separately named proof revision. The helper has no write access path into earlier
stage artifacts or actual templates.

## PowerShell

From any directory, use the installed interpreter:

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpProof = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_gallery_proof.py'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpProof
```

## Anaconda Prompt or CMD

No new Conda environment or model installation is needed:

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_gallery_proof.py"
```
