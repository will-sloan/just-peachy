# Supervised coordinator for selected same-Controller restart pairs

Purpose: collect each pair in a fresh, owned private-desktop process through the
existing exclusive slot, suspended Windows Job and renewable child admission.
Within each child the qualified lifecycle retains one Controller/UI/model store
for its two source sessions. This coordinator does not rewrite the earlier
single-source runner or weaken any existing resource or child-admission gate.

Inputs are a genuinely admitted restart PLAN.json reconstructed from reviewed
full-bank/mode scores, selected configurations and the V3 paced panel plan; the
fixed qualified interpreter and child script; and existing supervision state.
The parent manifest includes all helper dependencies. Only the unchanged 122
child records enter PERMIT.json, below its unchanged 128-record limit. The child
command is `restart_application_child.py --permit ... --nonce ...`; it has no
`child` subcommand. CPU4 is assigned before resume. The parent remains on CPU14.

`prepare` writes a fresh ADMISSION.json and worker.json but launches nothing.
The existing supervisor must admit that worker after previous exact owners have
exited and prerequisite reviews pass. `run` verifies its own supervised identity
and reconstructs the plan again, then collects rows sequentially. It checks the
exclusive slot before lease renewals. The child lifetime is bounded to 1,200
seconds; its internal pair lifecycle retains the stricter 900-second bound.
Failure cleanup permits 150 seconds of graceful exit before the existing owned
Job cleanup applies. The coordinator never controls the input desktop.

After normal process closure, the coordinator independently validates the saved
lifetime against the exact script/interpreter/argv/desktop/CPU/owner and verifies
the child result, full input and deterministic restart controls. It invokes
restart_pair_evidence on both released sessions. Post-exit checks preserve the
same supervisor/coordinator identity, disk floors, original reserve/deadline and
512-MiB cell limit without incorrectly requiring the exited root to remain live.
The slot releases only after the Job is empty and all observed child identities
have exited. Unknown descendants retain the slot and produce failed evidence.

Outputs are fixed transport records, the child application's two session
directories, PAIR_EVIDENCE_REVIEW.json, COLLECTED.json, PARENT_CLOSURE.json,
per-row progress and terminal RESULT.json. A late slot-release failure can leave
COLLECTED.json alongside a failed parent closure; this is not a passing run.
An existing terminal attempt is never reused. Independent full transport review
must check every parent closure and the exact complete selected pair population.
Viewport attribution, resource samples, timing/quality and functional acceptance
remain separate. Collection success never marks N4, N5 or CM5 integration done.

## Model-free development checks

The probe runs 24 checks: unchanged supervisor lease-order/timeout/exit-race
logic; exact child entrypoint and split manifests; spawn/register/resume/lease/
cleanup/descendant failures; rejected foreign/failed/accepted child or pair
results; post-exit policy checks; preparation without launch; complete/partial
run receipt handling and terminal-attempt preservation. Slot, private process,
lease writing, plan admission, supervision and downstream lifetime/pair readers
are mocked in the wiring fixtures. No positive production admission, actual
Windows private process, GUI, saved-audio run, model or Pi is exercised here.
The prior native-process and leaf-reader qualifications remain independently
bound; mocks do not add native execution evidence.

Probe inputs are existing qualifications and exact interpreter/code bindings.
Outputs include PROBE_OWNER, ADMISSION, source snapshots, tests.txt, preserved
synthetic fixtures and RESULT or FAILED in a new private directory. It uses the
writer lock, CPU14 below normal priority, one math thread/GPU off, healthy D1
checks, minimum C:50/G:75 GiB, shared allowance, 720 seconds and 8 MiB. Preserve
all previous attempts and increment the output suffix for a rerun.

PowerShell (no installation or environment activation needed):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_restart_runner.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-runner-probe-v1'
```

CMD and Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_runner.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-runner-probe-v1"
```

## Later preparation and supervised execution

These commands require RESTART_RUNNER_CHECK_V1.json and an actual admitted plan.
The plan and output below are placeholders, not existing production evidence.
Use the absolute plan path returned by restart_application_plan preparation and
a new private output directory. Do not run during D1 or another active model run.

PowerShell preparation:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B restart_application_runner.py prepare --plan '<admitted restart PLAN.json>' --output '<fresh private n4 run directory>'
```

CMD / Anaconda preparation:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B restart_application_runner.py prepare --plan "<admitted restart PLAN.json>" --output "<fresh private n4 run directory>"
```

Use the existing campaign supervision interface with the emitted worker.json.
It supplies `restart_application_runner.py run --admission <ADMISSION.json>` on
the exact supervised CPU14 owner. This internal run command cannot be launched
as an unrelated manual process. Do not invent a permit/nonce, edit the shared
ledger, switch a healthy active worker or bypass unresolved census ownership.
Live on-device installation and integration remain deferred until Pi reconnect.
