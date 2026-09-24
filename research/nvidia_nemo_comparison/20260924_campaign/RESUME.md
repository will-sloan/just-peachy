# Continue safely after N1

Use `N1_HANDOFF.md`, `N1_METRICS.json`, `FRONTEND_FREEZE.json`, the model/access
matrix and `local\supervision\campaign.json` as the current state. Reuse the
existing campaign branch/worktree; do not start a duplicate N1 or reset the
original checkout. Campaign start is 2026-09-24T14:48:19.949192+00:00 and the
96-hour target is 2026-09-28T14:48:19.949192+00:00, with 12 hours reserved for
packaging. Reinitialization must preserve these times.

The authorized Codex session is `01a0d3df-f647-75f1-bd82-aab88c1f570b`. Resume
manually in this existing task. A suitable next message after N1 acceptance is:

> Continue N2 from the completed N1 handoff in
> G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign.
> Reuse the frozen common UI, accepted corpus, independent reference plan,
> staged official models and existing supervisor. Keep the Pi off and use only
> saved processed audio. Work in the background without controlling my desktop.
> Use Astra Ultra at Normal speed. Do not start another copy of the stage.

This is a resume instruction, not an already-dispatched N2 task. Consult the
separate N2 specification before its execution. No global-last CLI resume or
approval-bypass flag is used. The current task's actual model/speed is controlled
by the app; recorded requested settings do not prove a change in that UI.

Inspect code supervisor state without starting a model (PowerShell):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign'
$jpState='G:\Just_Peachy_N1\20260924_campaign\local\supervision'
& $jpPython -B "$jpCode\supervision\supervisor.py" probe --root $jpState
& "$jpCode\supervision\register_supervisor.ps1" -StateRoot $jpState -Action Inspect
```

CMD/Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\supervision\supervisor.py" probe --root "G:\Just_Peachy_N1\20260924_campaign\local\supervision"
```

Numerical checkpoint resume, only after proving no active owner, uses
`supervisor.py start --root STATE --spec supervision\baseline_worker_spec.json
--resume`. Completed audio cells are hash-verified and skipped. A source/model/
runtime/manifest change requires a new output directory; failed evidence is
retained. Do not rerun a completed N1 screen merely to fill time.

To stop the whole campaign's check-ins after all authorized stages finish, run
`register_supervisor.ps1 -StateRoot STATE -Action Remove`. This only removes the
three reserved N1 tasks and writes a removal receipt; it does not delete data,
releases or any other scheduled tasks. Local rollback selects the original
unchanged checkout or immutable baseline archive, with a separate data root.
