# Independent S6C tracker review fixtures

Purpose: exercise the actual new research_tracking_v3.py class independently of its author's tests. This runs no models, waveform processing, hardware or evaluation scorer. It does not change H2 or old S6B source. A copy of the exact reviewed v3 bytes is saved before import so concurrent owner edits cannot silently change the tested implementation.

Inputs: current or explicitly supplied v3 tracker source; unchanged historical research_tracking_v2.py helpers; the existing EDGE Python/NumPy environment. Outputs: a fresh report directory containing REVIEWED_TRACKER_SOURCE.py and CHECK_RECEIPT.json with every passed/failed fixture and source/script/README hashes. The script returns nonzero when any fixture fails. All failures remain evidence; use a new directory for a corrected source revision.

The fixtures cover eight modes, the 16/32/64/128/256 allocation limits, severe voice rejection, borderline rescue, strong voice relocation, a small sole-candidate conflict neighborhood, shared short/mature clean unions, original prefix invariance, archive reentry/overlap, shadow staging, actual successive-vector escrow/rollback/split, actual merge with explicit synthetic track-state setup, 401-observation long bounded chronology and typed/stale-input guards. The long fixture is model-free state growth; it is not native endurance or continuous XVF adaptation. Merge preconditions are deliberately constructed; the operation and following waveform-support accounting execute the real code.

## PowerShell

~~~powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
& $py "$sim\scripts\s6c_tracking_review_checks.py" --output "$sim\reports\S6C\20260910T123540Z\tracker_review\checks_v1"
~~~

## Anaconda Prompt / Command Prompt

~~~bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
"%S6C_PY%" "%SIM%\scripts\s6c_tracking_review_checks.py" --output "%SIM%\reports\S6C\20260910T123540Z\tracker_review\checks_v1"
~~~

Use --source with an exact alternative tracker path to review a preserved revision. The source must retain its sibling-package import contract; v2 helpers are imported from the existing app and separately bound. Output must stay within this S6C report namespace. No environment installation/activation, model download or production-default promotion occurs. The optional source_unchanged_during_check flag tells the coordinator whether the live source changed while the isolated snapshot was tested; only the recorded snapshot bytes are certified.

These are constructed numerical cases, not measured speaker errors or universal operating-envelope validation. Temporal modes need only demonstrate reachable competing actions in the tested weight neighborhood, not obey the same nominal threshold as a stateless method. The old voice-gate mode is an eligibility control, not a claim of byte-identical S6B combined-score mathematics.

