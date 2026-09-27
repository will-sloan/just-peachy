# Guarded selected-plan application family

Purpose: connect the actual guarded plan to hidden private desktop collection
and independent complete-population evidence review. Every V5 dependency stays
retained. This fresh family uses `paced_panel_plan_guarded_v2`, a 512-record
child manifest bound (still 256 KiB), and `paced_slot_guarded_v1` within one
guarded run budget. Five-second leases, 4-KiB lease records, CPU14 coordinator,
CPU4 child, application behavior and owned-child cleanup retain their previous
constraints. No microphone, playback, user-input takeover or Pi connection.

V7 preserves both V6 attempts and changes only the record reader. Windows
CreateFileW opens the existing file with READ, WRITE and DELETE sharing. The
read handle continues to see its complete old version when the coordinator
atomically replaces the directory entry. Handle ownership transfers to the
Python stream; both conversion failure paths close their owned resource.
Non-Windows reads retain the ordinary binary reader. Actual byte limits,
JSON decoding, ownership, monotonic sequences and five-second expiry are
unchanged. The V6 writer retains its 0.25-second/13-attempt bound, original
issue time, same pending file, and failure cleanup. No ACL changes are made.

Four additional Windows regressions reproduce a normal binary reader blocking
the whole retry window, keep a shared reader open through 100 atomic renewals,
verify both conversion-error paths close the handle, and verify malformed,
oversized and missing records fail safely. These establish a specific reader
fix; the process that blocked the failed V6 lease was not identified.
The unchanged V6 child reader is included as a bound comparison input for the
AST regression, alongside the complete retained parent source manifests.

The actual run must inherit the separately verified process-local PYTHONPATH
pointing to the campaign worktree. Record it in the immutable dispatch admission
and set it only in the calling Python process before supervisor.start; children
inherit it. Do not change the machine/user environment. See
README_APPLICATION_IMPORT_PATH_V1.md and APPLICATION_PANEL_LEASE_FAILURE_V1.json.

Inputs: qualified private `PLAN.json`, closed preparation proof, complete source
manifest, fixed application interpreter/source, and existing saved audio/model/
gallery bindings. A child receives the unchanged 13-field inference payload;
no truth, score or selection. Outputs stay in fresh private stage directories.

The probe has a 16-MiB/40-minute supervised allocation. It reconstructs the
actual plan and checks 94 regressions: child 19, runner 20, transport 18, cell 11,
population 10, family 8, nested allocation 8. Lifecycle/resource fixture facts
are synthetic; saved native lifetime receipts are also checked. No actual model
or audio source starts. Outputs: test logs, source snapshots, `FIXTURE_INPUTS.json`,
resource receipts and `RESULT.json` or preserved `FAILED.json`. A closed matching
`APPLICATION_FAMILY_CHECK_V7.json` is required before production execution.
Preparation alone is not qualification.

The runner takes one 2-GiB/four-hour allocation. Complete resource checks occur
initially, every 30 completed cells and finally, always between closed children.
During each cell, the slot checks exact owners, every known competing runtime,
disk floors, output bytes and cutoff. Cell bytes consume the run cap once;
there is no fixed pending estimate or manual shared-ledger edit. A failure
preserves the attempt and closes only its owned child. Four hours is a hard
bound, not an ETA; a partial result cannot be silently resumed or accepted.

The panel reader has a 16-MiB/two-hour allocation. It requires a stopped exact
producer, plan reconstruction, all planned cells/progress, matching permits,
delivery/native/widget histories and run resource proofs. It writes per-cell
coverage and identical `RESULT.json`/`REVIEW.json`. Coverage does not establish
semantic accuracy, names, timing limits, RAM/deployment tiers, continuity,
restart or N4 acceptance. Matching semantic/restart consumers remain necessary.

## PowerShell

First inspect current heartbeat, exact PID creation identities, unchanged source,
the previous terminal and fresh full resource census. Do not start another N4
worker. The continuation records an immutable spec and dispatch admission via
the existing supervisor. Do not execute application workers standalone.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
Get-Content 'G:\Just_Peachy_N1\20260924_campaign\local\supervision\worker.json'
Get-Content 'G:\Just_Peachy_N1\20260924_campaign\local\n4\application-family-v7-probe-worker.json'
```

After the admission prerequisites and dispatch receipt are recorded:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import sys; from pathlib import Path; p=Path('research/nvidia_nemo_comparison/20260924_campaign'); sys.path[:0]=[str(p/'n4'),str(p/'supervision')]; from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path('G:/Just_Peachy_N1/20260924_campaign/local/supervision'),Path('G:/Just_Peachy_N1/20260924_campaign/local/n4/application-family-v7-probe-worker.json')))"
```

The probe spec uses the exact interpreter, `-B`, absolute
`probe_application_family_v7.py` and these arguments:

```text
--plan G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-plan-guarded-v2\PLAN.json --output G:\Just_Peachy_N1\20260924_campaign\local\n4\application-family-v7-probe
```

Only after full probe PASS, exact owner closure and publication, admit a fresh
runner spec: exact interpreter, `-B`, absolute `paced_application_runner_v7.py`,
`run --plan <qualified PLAN.json> --output <fresh private run directory>`, with
cwd equal to this n4 directory. The command is checked exactly. After complete
collection/closure, admit the reader: exact interpreter, `-B`, absolute
`review_application_panel_v7.py`, `--run <closed run directory> --output <fresh
separate review directory>`. Use the same supervisor interface for each spec.

## CMD and Anaconda Prompt

The exact interpreter is required; another conda activation is unnecessary.
Use the same recorded admission prerequisites before the start line:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
type G:\Just_Peachy_N1\20260924_campaign\local\supervision\worker.json
type G:\Just_Peachy_N1\20260924_campaign\local\n4\application-family-v7-probe-worker.json
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import sys; from pathlib import Path; p=Path('research/nvidia_nemo_comparison/20260924_campaign'); sys.path[:0]=[str(p/'n4'),str(p/'supervision')]; from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path('G:/Just_Peachy_N1/20260924_campaign/local/supervision'),Path('G:/Just_Peachy_N1/20260924_campaign/local/n4/application-family-v7-probe-worker.json')))"
```

Record the returned exact owner identity in `STARTED.json`; never repeat a start
for an active worker. During actual application collection, do not start Python
diagnostic helpers: the exclusive slot treats them as competing runtimes. Read
existing receipts without launching an application. Source edits after binding
are prohibited. The campaign reserve/deadline stay fixed; CM5 checks are deferred.
