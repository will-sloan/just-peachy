# Native wrapper model-free fixtures

Purpose: test in-process protocol bridging and strict completion/stop semantics with a tiny fake engine exported by the fixture module. It imports no native speech application or models, plays no audio and touches no device. The fake helper's native_tested field is explicitly fixture data; fixture receipts state that no production native helper was invoked.

Inputs: current wrapper+shared supervisor+this fixture source, and a new output directory. Outputs: per-scenario frozen test manifests, fake native RESULT files, protocol heartbeats, failure/success receipts and NATIVE_WRAPPER_FIXTURE_RECEIPT.json. Same-process PID checks are real; the semantic source/queue data is simulated to exercise both valid and invalid behavior.

Checks include normal completion, undrained workers, live observer, pending consumer, native completion error, wrong PID, false COMPLETE status, missing checkpoint callback, actual matching STOP request calling fake engine.stop and ensuring no COMPLETE output, and100unchanged progress updates that must not increase progress_count. Existing output directories are rejected; use the next suffix on rerun.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6d_runner_native_pilot_fixtures_v1.py" --output "$sim\reports\S6D\20260913T195357Z\runner\native_wrapper_fixtures_v1"
```

Anaconda Prompt or Command Prompt (same existing interpreter, no conda activation):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_runner_native_pilot_fixtures_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\runner\native_wrapper_fixtures_v1"
```

These fixtures call the wrapper function directly in the fixture process; they do not run production jobs or create a subprocess. S6D_* environment variables are temporary fixture inputs and restored afterward. No account/session or OS power settings are changed.
