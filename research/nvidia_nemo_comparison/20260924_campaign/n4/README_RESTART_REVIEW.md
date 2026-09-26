# Independent review of a complete selected restart run

Purpose: verify the recorded transport and both sessions for every selected
restart pair after its coordinator and applications have stopped. This is an
explicit derivative of the earlier transport/population readers. Existing
qualified code and receipts remain unchanged. Nothing here starts a GUI, model,
audio source, device or Pi, or modifies the reviewed run.

`review_restart_transport.review_cell` accepts one cell directory plus a payload,
plan digest, exact stopped coordinator, separate child and parent manifests,
qualified interpreter, coordinator command and supervision path reconstructed by
the run reviewer. It verifies fixed child arguments without the old subcommand;
normal private-desktop/CPU4 process closure; the terminal lease and its sequence;
exact slot owners, inventory, input/child/result/preparation joins; both manifest
digests; and every parent cleanup/release receipt. A COLLECTED.json with a late
cleanup failure cannot pass. The saved pair review must equal a new independent
read of its fixed delivery, engine/archive, native and pair evidence. Shared
bindings must agree and all are rechecked before return.

Historical limitations stay explicit. The final lease does not reconstruct all
renewals. Process accounting can contain unsampled assignments. Recorded common
Controller/UI/worker/model joins do not add independent object instrumentation.
Passing transport/evidence review does not qualify viewport rows, resource
samples, latency, naming/accuracy, functional restart acceptance or a device.

`review_restart_run.py` is the production entry point. Inputs are an actual
stopped run directory from restart_application_runner and a new private output
directory outside that run. It checks preparer/coordinator identities, worker
command, qualified split manifests and interpreter, then reconstructs the actual
accepted plan through restart_application_plan.admit_plan. Baseline plus at most
five selected alternatives must each have exactly one O0 and O1 anchor pair,
two sessions per pair, the fixed midpoint policy and zero integrated-cell credit.
Missing, additional, duplicated, reordered, failed or promoted receipts fail.
The file/directory census is checked again after every cell review finishes.

Outputs are REVIEW_OWNER.json, ADMISSION.json, complete per-pair review JSON files
and REVIEW.json, or FAILED.json with preserved partial output. Successful status
is PASS_COMPLETE_RESTART_EVIDENCE_COVERAGE_ONLY. It proves complete planned
evidence coverage within the declared limits; it does not set N4/N5 acceptance.
Source evidence stays private, including raw native history and caption data.

## Development probe

`probe_restart_review.py` consumes the qualified coordinator and seven saved
native process lifetimes. It runs 29 tests: inherited transport corruption and
failure cases, split manifests, fixed child argv, independent reread mismatch,
late cleanup failure, exact minimum/maximum selected populations, malformed or
partial receipts, fixed anchor/stop policy and stopped-run command/owner gates.
Synthetic PID existence, the pair leaf reader and production plan admission are
mocked in their respective fixtures. The seven existing native lifetime cases
are reread with real current OS identity checks; no new process is spawned.
No actual production plan or complete production run is manufactured.

Probe outputs are source snapshots, PROBE_OWNER, ADMISSION, tests.txt, preserved
synthetic records and RESULT or FAILED in a fresh private folder. The probe uses
CPU14 below normal priority, math threads=1/GPU off, writer lock, fresh D1 ownership
checks, C:50/G:75 GiB floors, shared allowance, 720 seconds and 8 MiB. The later
production review has a 3,600-second/8-MiB budget with the same deadline/floor
guards. Existing attempts remain immutable; increment suffixes for reruns.

PowerShell (use the existing exact environment, no installation needed):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_restart_review.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-review-probe-v1'
```

CMD and Anaconda Prompt (explicit interpreter, no activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_review.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-review-probe-v1"
```

## Later complete-run review

These placeholders require real accepted predecessor evidence and the published
RESTART_REVIEW_CHECK_V1 qualification. Substitute the stopped runner output and
a distinct fresh private review directory. Neither placeholder represents an
existing production result. Do not review an active coordinator or application.

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_restart_run.py --run '<stopped admitted restart run directory>' --output '<fresh private n4 review directory>'
```

CMD and Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_restart_run.py --run "<stopped admitted restart run directory>" --output "<fresh private n4 review directory>"
```

Actual collection still follows full D1/main/mode bank review, scoring and
configuration selection. Viewport attribution/resource/timing interpretation
and actual functional acceptance remain. The Pi stays off during this campaign;
on-device installation and integration checks wait for the user's reconnect.
