# Selected restart family for the V4 scored panel

## Purpose and files

This fresh derivative connects the V4 scored selected-panel plan to the existing
two-session, same-controller restart application. The baseline and each selected
alternative retain both fixed O0/O1 anchors: 2–12 pairs and 4–24 sessions. Session
one stops at the qualified midpoint; session two replays the full saved file.
Preparation and evidence coverage do not grant functional, timing, resource,
N4 or N5 acceptance.

`restart_family_v2.py` binds all parent qualifications and the complete source
closure, and admits only its exact completed development proof.
`restart_application_plan_v2.py` reconstructs the V4 selected panel and writes
schema `n4-restart-application-plan-v2` with unchanged 13-field child inputs.
`restart_application_runner_v2.py` prepares schema `n4-restart-application-run-v2`
and coordinates the unchanged 122-file restart child closure. Its larger parent
manifest is never substituted for the child permit. The child, original
128-record permit limit, 256-KiB permit/input bound, five-second lease, source
policy, CPU4 child placement and private desktop are unchanged. The family
parent manifest has a 512-record ceiling; every actual record remains hashed.
`review_restart_run_v2.py` reconstructs the exact stopped preparer/coordinator,
plan, command and complete population. `review_restart_content_run_v2.py` joins
the unchanged transport/lifecycle, fixed display roster, source delivery,
native caption and viewport readers for every planned pair.

The five `test_restart_*_v2.py` files cover planner, coordinator, stopped-run,
content/population and cross-version invariants. `probe_restart_family_v2.py`
runs them without a real application, model, microphone, playback or Pi.
Coordinator/child/slot and lifecycle leaves are mocked where documented.
Content readers use synthetic native/viewport/roster facts. Stopped-run fixtures
mock plan and qualification admission and use explicitly fictitious owners.
They do not establish a successful production admission or real restart.

## Inputs and outputs

Development inputs: exact preserved parent qualification receipts, frozen
application source/context, two saved anchor hashes/WAV headers, source manifests
and live main-bank ownership/resource snapshots. Synthetic planner fixtures carry
saved component asset metadata so they exercise the real child input-schema gate;
this probe does not reload or revalidate model-weight contents. Outputs are private immutable
source snapshots, bounded fixtures, test logs, `ADMISSION.json`, `RESULT.json`
or preserved `FAILED.json`. The parent `RESTART_FAMILY_CHECK_V2.json` is sealed
only after checks pass and the exact helper process has exited.

Production inputs: a fully admitted V4 plan derived from complete reviewed main
and modes banks and explicit selection; the original saved audio/assets; exact
supervised owner and exclusive controlled slot. Outputs: plan/worker receipts,
pair application/transport evidence, stopped-run and complete content reviews.
The content reviewer has a one-hour/64-MiB bound; it reserves failure space before
writing each receipt. Every output must use a fresh private directory.

## PowerShell

From the campaign worktree, with the admitted application environment:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4 = 'research\nvidia_nemo_comparison\20260924_campaign\n4'
$env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'
$env:CUDA_VISIBLE_DEVICES='-1'; $env:PYTHONDONTWRITEBYTECODE='1'
& $jpPython -B "$jpN4\probe_restart_family_v2.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-family-v2-probe-v1'
```

The probe pins itself to CPU14/BelowNormal, uses the existing metadata-writer
lock, allows 20 minutes/8 MiB, checks C50/G75 floors, reserves the remainder of
the active V3 bank allocation and preserves the packaging cutoff. A failed
attempt stays intact; use a new output suffix for an investigated repair.

After complete main/modes review, selection and V4 plan admission:

```powershell
& $jpPython -B "$jpN4\restart_application_plan_v2.py" --panel-plan 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-panel-plan-v4\PLAN.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-restart-plan-v2'
& $jpPython -B "$jpN4\restart_application_runner_v2.py" prepare --plan 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-restart-plan-v2\PLAN.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-restart-run-v2'
```

Preparation writes `worker.json`; it starts no application. Only the existing
authorized supervisor may dispatch that worker after the exact exclusive-slot
and resource admission pass. Do not run the child/coordinator manually, launch
a visible application, change shared ledgers or bypass an inaccessible process.
When the entire run and exact preparer/coordinator have stopped:

```powershell
& $jpPython -B "$jpN4\review_restart_run_v2.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-restart-run-v2' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-restart-transport-v2'
& $jpPython -B "$jpN4\review_restart_content_run_v2.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-restart-run-v2' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-restart-content-v2'
```

## CMD and Anaconda Prompt

Both use the already admitted interpreter explicitly; do not change Conda
packages or install another runtime. The same commands work in either prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set CUDA_VISIBLE_DEVICES=-1
set PYTHONDONTWRITEBYTECODE=1
"%JP_PYTHON%" -B "%JP_N4%\probe_restart_family_v2.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-family-v2-probe-v1
```

For production preparation/review, substitute the corresponding script and
arguments from PowerShell above, using `"%JP_PYTHON%" -B "%JP_N4%\SCRIPT.py"`.
Never reuse an existing output directory. Keep all private audio, profiles,
weights and full evidence outside Git. The Pi remains offline. Live CM5 checks
are deferred until reconnection. Packaging begins 2026-09-28 02:48:19 UTC and
the campaign ends 14:48:19 UTC that day; these scripts do not extend either.
