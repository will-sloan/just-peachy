# Separate historical B36 paced control

`s6c_paced_b36_v1.py` adds40 current paced cells for exact historical B36:
the original tracker under the S6B common causal scheduler. It uses the full
sealed epoch2 B36 profile, R0 frontend, `original_common`, original capacity256,
cue-off, and all original model/thread/endpoint/numeric settings. It is distinct
from immutable default B00 and the B01 voice method. It does not substitute a
new S6C profile for B36.

Inputs: exact existing80-cell B00/B01 plan, sealed S6B epoch2/profile/asset/input
bindings, original paced worker/optional-LIVE observer, and a fresh namespace.
The new jobs keep the same16 first-pass and4 repeat cases, both taps, whole
once-gained files and case order. Each B36 native session starts fresh as the
original driver specifies. Native algorithm/driver bytes are unchanged. The
existing B00/B01 plan, admission, files and source remain untouched.

Sixteen original coordinator functions—including quiet/resource checks, sampled
process trees, the native run loop, optional-LIVE observation and owned cleanup—
are copied with exact AST parity. B36-specific preparation/admission checks are
new and explicitly bound. The runtime invokes the original `s6b_paced.py --mode
worker` and keeps strict final PCM/cursor/journal checks. Optional sampled LIVE
missingness remains distinct from authoritative output failure. The original
driver's cold-start/model-loading scopes and sampled memory limits still apply.

Outputs: fresh `G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json`
and report preparation/fixtures. A later authorized run produces per-cell
LAUNCH/WORKER_RESULT/PROCESS_SAMPLES/COMPLETE, native journals/events and a bound
invocation completion. The run needs a separate matching quiet admission with
an expiry; it never creates its own authorization or starts while owned study
workers remain. Unrelated user processes are not stopped. No launch is implied
by preparing this manifest.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython "$s6cSimulation\scripts\s6c_paced_b36_v1.py" checks
& $s6cPython "$s6cSimulation\scripts\s6c_paced_b36_v1.py" prepare --namespace b36_v1
# Execute only after independent review and a root-supplied quiet admission:
& $s6cPython "$s6cSimulation\scripts\s6c_paced_b36_v1.py" run --manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json' --quiet-admission "$s6cSimulation\reports\S6C\20260910T123540Z\paced_controls\b36_v1\QUIET_ADMISSION.json"
```

Anaconda Prompt / CMD:

```bat
set "S6C_SIMULATION=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set PYTHONDONTWRITEBYTECODE=1
"%S6C_PYTHON%" "%S6C_SIMULATION%\scripts\s6c_paced_b36_v1.py" checks
"%S6C_PYTHON%" "%S6C_SIMULATION%\scripts\s6c_paced_b36_v1.py" prepare --namespace b36_v1
REM Execute only after review and the separate source-bound quiet admission.
"%S6C_PYTHON%" "%S6C_SIMULATION%\scripts\s6c_paced_b36_v1.py" run --manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json" --quiet-admission "%S6C_SIMULATION%\reports\S6C\20260910T123540Z\paced_controls\b36_v1\QUIET_ADMISSION.json"
```

`checks` imports only metadata/original worker code and executes no model or
engine. A completed fixture namespace is preserved. Source duration is about
29.8minutes, excluding startup/admission/observer overhead. Time bounds retain
the source plan's stage reserve; incomplete launches require explicit diagnosed
recovery. This is a desktop paced control, not a CM5 timing qualification.
