# Bounded S6B actual-neural component smoke

`s6b_component_neural_check.py` snapshots the current application and validated
neural recipe registry into a new output directory before imports. It then runs
seven sequential fresh sessions in one process: an 18-second R0 prefix pair with
identical first12seconds/different future, an identical resident repeat,
R3_SHORT_LONG, R5 debt, endpoint-only, and modified-beam R7 at50ms. Each input
contains107additional samples to exercise a real partial EOF delivery. Native
state, model outputs and artifacts are real. This is bounded smoke evidence,
not full-bank accuracy evidence. Output comparison reports model/word/tracker/
display parity separately, excluding measured timing from semantic comparisons.

Input WAVs must be prepared mono16k and the primary input at least18seconds.
Optional sanitized telemetry uses the same source time; omitting it executes an
empty-cue endpoint path and does not claim real endpoint proposals activated.
The endpoint limiter activation itself is covered by separate component fixtures.
The script validates fixed asset bytes once per resident recipe bundle, creates
new Sherpa stream and all fresh session state per scene, and records actual model
loading separately. The immutable snapshot relocates only repository/evaluation
root paths for asset resolution. No source is modified after snapshotting.

Outputs are RECEIPT.json, periodic HEARTBEAT.json, source/profile/code bindings,
prepared test WAVs, an app snapshot, and complete native session artifacts under
the supplied new output directory. The compact receipt is copied to
REPORT/COMPONENT_NEURAL_SMOKE.json. Retain failed attempts; choose a new output
directory for an explicitly authorized retry. There is no deletion or resume
that silently substitutes outputs. Each session has a120second bounded timeout.
For the explicitly approved B34 structural configuration repair, add
`--jobs R3_SHORT_LONG --receipt-name COMPONENT_NEURAL_REPAIR_B34.json
--source-app "G:\Just_Peachy_S6B\20260909T230840Z\component_smoke_v1\app\edge_speech_pipeline"
--repair-of "G:\Just_Peachy_S6B\20260909T230840Z\component_smoke_v1\RECEIPT.json"`
to the same command, changing output to `component_smoke_b34_repair_v1`. This
uses the same immutable code/audio with the prospectively repaired registry's
contiguous clean threshold .45s instead of the unreachable .5s on a .5s early
window. It preserves the original zero-embedding attempt and its binding.

## PowerShell

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_component_neural_check.py' --repo 'C:\Users\amiri\Documents\GitHub\just-peachy' --report 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z' --output 'G:\Just_Peachy_S6B\20260909T230840Z\component_smoke_v1' --input 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_01_01\O0.wav' --endpoint-input 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_03_01\O0.wav'
```

## Anaconda Prompt or Windows Command Prompt

No environment activation is needed because the interpreter path is explicit.

```bat
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6b_component_neural_check.py" --repo "C:\Users\amiri\Documents\GitHub\just-peachy" --report "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6B\20260909T230840Z" --output "G:\Just_Peachy_S6B\20260909T230840Z\component_smoke_v1" --input "G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_01_01\O0.wav" --endpoint-input "G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_03_01\O0.wav"
```

The script fixes OMP/OpenBLAS/MKL/NumExpr pools to1before native imports. This does
not assert a global OS thread cap or CM5 real-time performance. All runs are
accelerated; actual paced native repetitions remain a separate S6B measurement.
