# Coordinator-only exact scan overlay

`s6c_orchestrator_scan_v1.py` is a separately bound orchestration layer around
the unchanged frozen epoch2 native runner. It replaces only the coordinator
process's `s6c_common.tree_bytes` callable with the reviewed exact current-scan
implementation. Original worker initialization/execution, model extraction,
validation, reuse checks, pool code, native identities and all other admission
checks remain unchanged. No time cache or approximation is introduced.

The wrapper verifies its admission, own source/README, scanner/README, exact
epoch2 sources/assets and interpreter/package versions. Original modules must
not be preloaded. They are imported from frozen epoch2 first. Fresh spawned
workers resolve those original modules; the overlay is never installed in a
worker. The original scanner is restored even on exceptions. A distinct
orchestration name and receipt preserve the fact that coordinator code differs
from the original invocation while native job identities remain epoch2.

Inputs: the exact existing epoch2 job manifest; one to four workers; the reviewed
scanner fixtures/benchmark; all prior epoch2 invocation files. The run guard
requires prior invocation owner and recorded remaining-process identities to be
closed. Original workers may finish durable jobs during a graceful checkpoint;
their complete receipts will be verified by the unchanged resume path. The
wrapper does not stop processes, clear STOP_REQUEST, select jobs, or overwrite
failed attempts. The root coordinator owns checkpointing and later launch.

Outputs under `reports/S6C/20260910T123540Z/orchestration/<name>`: immutable
ADMISSION, STARTED with PID/creation/argv and all prior invocation provenance,
and CLOSURE binding the newly produced original native invocation artifacts.
The original runner also retains its original epoch2 worker/receipt/closure
outputs. Owner process exit is checked externally after CLOSURE is written.

PowerShell (prepare/test do not run models):

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$s6cReport = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z'
Set-Location -LiteralPath $s6cScripts
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython s6c_orchestrator_scan_v1.py test --name v1
& $s6cPython s6c_orchestrator_scan_v1.py prepare --jobs "$s6cReport\jobs\epoch2\recipes_v1.json" --workers 4 --name recipes_scan_v1
# Only after independent review, graceful old-pool closure and root admission:
& $s6cPython s6c_orchestrator_scan_v1.py run --admission "$s6cReport\orchestration\recipes_scan_v1\ADMISSION.json"
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
set "S6C_REPORT=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_orchestrator_scan_v1.py test --name v1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_orchestrator_scan_v1.py prepare --jobs "%S6C_REPORT%\jobs\epoch2\recipes_v1.json" --workers 4 --name recipes_scan_v1
REM Only after reviewed root launch admission:
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_orchestrator_scan_v1.py run --admission "%S6C_REPORT%\orchestration\recipes_scan_v1\ADMISSION.json"
```

Each new attempt needs a fresh orchestration name. A model-free child-import
fixture proves that a fresh interpreter sees the original frozen scanner and
worker module. It is not a model or full ProcessPool execution claim. Hashes are
still checked by the original runner before reuse and execution; this layer
does not cache model/input hash results. It does not alter APP, profiles, model
weights, source pacing, endpointing or policy scheduling. Unrelated user
processes remain untouched.
