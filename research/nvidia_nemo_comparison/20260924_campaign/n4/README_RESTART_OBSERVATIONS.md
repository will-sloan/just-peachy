# Restart viewport and resource attribution

`review_restart_observations.py` independently reconstructs the two closed
viewport ledgers and the pair's process resource log. It assigns captions to
their recorded caption-key session and retains the original source clock for
old captions visible during the second session. Unknown/future sessions and
row/span identity collisions fail. Every recorded row version is examined,
including rows later removed from the Controller. First visibility is reported
per ledger; visibility between ledgers is not assumed continuous.

Resource samples are assigned to a session only when their entire measurement
interval falls inside that session's source-to-release interval. Crossing and
outside samples have separate counts. The shared `running` label spans both
sessions and is not treated as a per-session boundary. Missing PSS and missing
complete samples remain unavailable. RSS, USS and private commit stay separate.
The sample window includes engine drain, and its differences are not a leak
diagnosis or model cost. No pacing correction is subtracted from times.

## Inputs and outputs

The internal `review_observations(application, payload=..., application_owner=...,
checkpoint=...)` API takes one closed private `application` directory, the
independently reconstructed full planned payload, and its exact exited process
identity. It first invokes the qualified pair reader, then joins preparation,
both session snapshots, source/release times, viewport geometry/callback counts,
and the actual raw resource records. Inputs are bound again after reading.
The return value includes both viewport partitions, per-session resource sample
counts/peaks, unchanged leaf reviews, final Controller/viewport span censuses and
evidence hashes. Caller must persist this result privately and independently
verify supervised transport and the exact selected production population.

The API is an observation component, not an executable production admission
command. The earlier `review_restart_run.py` remains frozen and does not invoke
this new component. Integration into a fresh qualified run reviewer is pending.

`probe_restart_observations.py` takes a **fresh** private output directory and
requires the original healthy D1 worker. It pins this lightweight helper to
CPU14 at BelowNormal priority with one math thread, checks free-space/time/private
inventory limits, uses the existing writer lock, and preserves source snapshots,
ADMISSION, PROBE_OWNER, tests.txt, all synthetic fixture files and RESULT or FAILED.
It does not start a GUI, inference worker, audio source or remote connection.

`test_restart_observations.py` has 22 checks using generated saved synthetic
logs and the real ledger/resource readers. The two composition tests mock the
already-qualified pair reader and prepared-context resolver only. No actual
production restart, model output or native caption payload is validated by
these tests. The schema partition is explicitly not independent native caption
content attribution. Functional semantics, acquisition/latency thresholds,
controlled resource qualification and N4/N5 acceptance remain pending.

## PowerShell

Run from the campaign N4 directory using the admitted Python environment:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\probe_restart_observations.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-observations-probe-v1'
```

## CMD

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_observations.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-observations-probe-v1"
```

## Anaconda Prompt

Use the same CMD commands above with the explicit interpreter. Do not install
packages or change the active campaign environment. If that evidence directory
exists, choose a new suffix and preserve the existing attempt. Direct unguarded
unittest execution is unsupported; the probe supplies its private fixture root.

The public development qualification binds only code/document hashes and private
receipt bindings. Synthetic fixtures and all actual observations remain private.
No source bound to D1, prior qualified runner, release or prior failed attempt
is edited. The Pi stays off; this work does not establish live CM5 integration.
