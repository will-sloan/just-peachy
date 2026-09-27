# Guarded restart family V3

Status: implementation prepared on 2026-09-27; qualification and actual execution
are pending. Do not launch these entry points until their complete development
probe passes, the exact probe processes close, and a matching
`RESTART_FAMILY_CHECK_V3.json` is published. Preparation is not N4 acceptance.

Purpose: carry the existing two-session, same-controller restart experiment from
the fully reconstructed guarded 240-cell panel into a bounded supervised run.
Each of six selected configurations uses both fixed saved tap anchors: stop at
the fixed midpoint, then restart the complete file in the same controller. This
produces 12 pairs / 24 sessions. No microphone, playback, training, enrollment,
visible desktop, network connection, or Pi access is involved.

The derivative preserves the qualified 122-record child manifest, 13-field
audio-only input, original pair review, native-caption, roster, viewport and
resource readers. Its parent uses V6's bounded lease replacement and existing
guarded slot. Cell reservations sit inside the run allocation and are not added
again. Every executable role records initial/final full resource censuses;
the runner refreshes between groups of four closed pairs. A failed run preserves
its terminal, cells and cleanup evidence. No failed or partial population passes
the complete reviewer. The envelope grants no source-execution permission.

## Files, inputs and outputs

- `restart_family_v3.py`: full parent lineage, fixed role budgets, qualification
  and closed-producer joins. Inputs are unchanged qualified parent receipts.
- `restart_application_plan_v3.py`: `--panel-plan` from the qualified guarded
  producer and fresh `--output`; writes ADMISSION, EXECUTION_PLAN, PLAN, RESULT.
- `restart_application_runner_v3.py`: `run --plan <restart PLAN.json> --output
  <fresh directory>`; writes per-pair lifetimes, input/lease, original application
  artifacts, evidence joins, progress and terminal RESULT.
- `review_restart_transport_v3.py`, `review_restart_complete_v3.py`, and
  `review_restart_content_cell_v3.py`: internal stopped-evidence APIs, not launchers.
- `review_restart_run_v3.py` and `review_restart_content_run_v3.py`: `--run <closed
  run> --output <fresh separate directory>`; write inputs, pair reviews, REVIEW
  and guarded RESULT. Coverage checks require subsequent functional interpretation.
- `test_restart_guarded_v3.py` and `probe_restart_family_v3.py`: intended 81 retained
  compatibility tests plus 20 new tests, actual 240-cell plan reconstruction and
  all 12 derived child payloads. Inputs are `--plan` and fresh `--output`; outputs
  include test logs, source snapshots, reconstructed plan, guards and RESULT.

Limits: probe/preparation 16 MiB and 40 minutes each; actual run 2 GiB and two
hours; each reviewer 64 MiB and one hour. CPU14 coordinator, CPU4 application,
BelowNormal, math threads one, GPU disabled. Original packaging reserve,
deadline and C50/G75 GiB free-space floors continue to apply. The process-local
PYTHONPATH must include the campaign worktree for the accepted N3 archive import.

## PowerShell

Use the existing supervisor and a fresh immutable worker spec/dispatch receipt.
Inspect current heartbeat, exact process creation identities, source hashes and
fresh complete resource census before dispatch. Do not run during another actual
application evaluation. The older scheduled Python probes must remain absent
during the exclusive application window; their saved XML and removal receipt are
in `local/n4/scheduled-probe-isolation-v1`. The hourly Codex heartbeat continues.

```powershell
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpWork='G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
Set-Location "$jpWork\research\nvidia_nemo_comparison\20260924_campaign\n4"
Get-Content "$jpLocal\supervision\worker.json"
$env:PYTHONPATH=$jpWork
```

Prepare the spec as an explicit argv array using the exact interpreter, `-B`,
absolute script, and arguments above. The first permitted spec is the development
probe, with the existing guarded panel as `--plan`; its output directory must not
exist. After the independently checked dispatch receipt is recorded, start it:

```powershell
$jpSpec='<absolute fresh admitted worker spec.json>'
& $jpPy -B -c "import sys; from pathlib import Path; sys.path.insert(0,str(Path('../supervision').resolve())); from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path(sys.argv[1]),Path(sys.argv[2])))" "$jpLocal\supervision" $jpSpec
```

`start` creates the hidden host. Do not use an alternate interpreter or bypass
the guard by invoking an actual worker directly. After a closed positive probe,
publish only verified qualification bindings, then dispatch preparation, actual
run, transport review and content review sequentially. No existing output is reused.

## CMD / Anaconda Prompt

No conda activation is required; use the same pinned interpreter and admissions:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_WORK=G:\Just_Peachy_N1\20260924_campaign\worktree"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
cd /d "%JP_WORK%\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "PYTHONPATH=%JP_WORK%"
type "%JP_LOCAL%\supervision\worker.json"
set "JP_SPEC=<absolute fresh admitted worker spec.json>"
"%JP_PY%" -B -c "import sys; from pathlib import Path; sys.path.insert(0,str(Path('../supervision').resolve())); from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path(sys.argv[1]),Path(sys.argv[2])))" "%JP_LOCAL%\supervision" "%JP_SPEC%"
```

Keep private WAVs, models, profiles and evidence out of Git. The new sources are
unbound until admitted; any later edit after admission requires a fresh derivative.
