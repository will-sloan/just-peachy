# Model-free S6D supervisor fixtures

Purpose: exercise the frozen queue supervisor without production jobs, models, device I/O, account changes, automation or host keep-awake changes. The fixture script also acts as the tiny child used in subprocess tests; it writes only its explicit local fixture heartbeat/completion/result files. It uses the existing Python interpreter and psutil.

Inputs: s6d_runner_v1.py, this fixture script and a new output directory. The fixture creates exact approved test queues/approval hashes for its own tiny Python children only. Outputs: scenario queues, approvals, child/health logs, checkpoints, simulated hardware block/restoration files and FRAMEWORK_FIXTURE_RECEIPT.json. Expected failure artifacts and blocked states remain preserved; they are not production failures or hardware evidence.

Coverage: normal completion, completed-job resume with no rerun, stale heartbeat while PID is alive, actual declared progress stall, exited/reused PID, partial JSON recovery/permanent truncation, missing completion, false scientific predicate despite exit0, failed child, auth/quota without retry loops, owned offline termination after STOP_REQUEST grace, exclusive supervisor lock, strict argv/cwd/output/source checks, simulated unresolved hardware restoration with no termination, simulated keep-awake ownership/restoration failure, 2048byte delta cap and changed completed-artifact rejection.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6d_runner_fixtures_v1.py" --output "$sim\reports\S6D\20260913T195357Z\runner\framework_v1"
```

Anaconda Prompt or Command Prompt (no conda activation):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_runner_fixtures_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\runner\framework_v1"
```

Choose framework_v2, v3, etc. when the prior directory exists; tests never delete or overwrite prior results. The --child-mode and --result switches are internal fixture interfaces requiring S6D_* identity/output environment variables from the supervisor. They should not be used to run arbitrary code. The deliberate hold fixture can run20seconds if started alone; under the test it receives a0.3second deadline, a STOP_REQUEST grace and exact owned-child termination. No unrelated process is terminated. Fixture health is accelerated through the Python API under fixture_only=true; the production CLI retains15second health and30second heartbeat.

The first framework_v1 run exposed a normal child-exit race between PID inspection and process-tree memory sampling. Its outputs and source epoch are preserved. Resource sampling now treats that psutil.NoSuchProcess as an unavailable sample and proceeds to authoritative completion validation.

Root review added finite-number checks, Windows case-insensitive environment identity protection, fixed campaign start/end with45minute closeout reserve, enforced C50/G75GiB production floors, prelaunch deadline rejection and a synthetic deadline crossing during health. Those fixtures run in the next fresh framework output and preserve the earlier16-group receipt. Large model assets are excluded from repeated small-code hashing; no models are loaded by these tests.
