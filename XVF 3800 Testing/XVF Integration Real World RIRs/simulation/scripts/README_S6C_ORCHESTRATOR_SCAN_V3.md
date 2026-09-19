# Pinned additive-epoch coordinator V3

`s6c_orchestrator_scan_v3.py` admits explicitly trusted epoch2 or epoch4 and
reuses the separately reviewed exact scanner in the parent coordinator only.
Epoch4 SHA is pinned, and its complete APP inventory, whole native worker and
common modules, models, environment and canonical sources must equal epoch2.
It imports unchanged V2 overlay utilities; V2 and the scanner stay untouched.
Adding a future epoch requires a new reviewed wrapper version, not an arbitrary
command-line hash. The original frozen worker handles every actual job.

Inputs: exact admitted epoch, original epoch2, exact job manifest, explicit
worker count1..4, fresh orchestration name. Paced work requires one worker.
The original run revalidates jobs, audio, profiles, galleries, assets and current
resources. Preparation is model-free and may occur while another epoch runs.
Before launch, recorded invocation owners/remaining children across all epoch
namespaces must be closed; missing/incomplete closure evidence rejects. A new
epoch's absent invocation directory is valid. No process is killed by this
wrapper, and no stop marker is removed.
This prior-invocation guard covers native epoch coordinator owners and recorded
remaining children. It is not a census or reservation system for separately
launched paced, long-session, HIL, analysis or unrelated user processes. The
caller must separately reserve a quiet interval and close applicable owned
research jobs before a paced launch; unrelated user processes remain untouched.

Outputs: immutable `orchestration/<name>/ADMISSION.json`, then `STARTED.json`
and `CLOSURE.json` when actually launched. Original native invocation/worker/job
receipts retain their existing schema and exact job identities. An interrupted
invocation remains; prepare a new orchestration name for an authorized resume.
Prior process checks cover recorded owner/remaining-child identities and native
pool joining, not a complete census of every historically spawned process.

The scanner enumerates current entries without a cross-call cache. Like the
original scan it is not an atomic global filesystem snapshot. Reservations and
every original storage/RAM/deadline/stop check remain in place. Optional Windows
junction/reparse equivalence is not established by the ordinary-directory tests.

PowerShell (prepare and review before using the separate run command):

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = "$s6cSimulation\reports\S6C\20260910T123540Z"
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:JP_S6C_SIM = $s6cSimulation
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython "$s6cSimulation\scripts\s6c_orchestrator_scan_v3.py" test --epoch epoch4 --name v3_ready
& $s6cPython "$s6cSimulation\scripts\s6c_orchestrator_scan_v3.py" prepare --epoch epoch4 --jobs "$s6cReport\jobs\epoch4\explicit_gate6_v2_rep1.json" --workers 4 --name epoch4_gate6_scan_v2
& $s6cPython "$s6cSimulation\scripts\s6c_orchestrator_scan_v3.py" run --admission "$s6cReport\orchestration\epoch4_gate6_scan_v2\ADMISSION.json"
```

Anaconda Prompt / CMD:

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%JP_S6C_SIM%\reports\S6C\20260910T123540Z"
set "S6C_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set PYTHONDONTWRITEBYTECODE=1
"%S6C_PYTHON%" "%JP_S6C_SIM%\scripts\s6c_orchestrator_scan_v3.py" test --epoch epoch4 --name v3_ready
"%S6C_PYTHON%" "%JP_S6C_SIM%\scripts\s6c_orchestrator_scan_v3.py" prepare --epoch epoch4 --jobs "%S6C_REPORT%\jobs\epoch4\explicit_gate6_v2_rep1.json" --workers 4 --name epoch4_gate6_scan_v2
"%S6C_PYTHON%" "%JP_S6C_SIM%\scripts\s6c_orchestrator_scan_v3.py" run --admission "%S6C_REPORT%\orchestration\epoch4_gate6_scan_v2\ADMISSION.json"
```

`test` performs source/admission/child-import checks only; it does not create a
neural worker or call `run()`. Do not use an already completed fixture/output
name for different source bytes. Resource timing from distinct orchestration
versions must retain that provenance. This is desktop research execution, not
hardware playback, production promotion or CM5 qualification.
