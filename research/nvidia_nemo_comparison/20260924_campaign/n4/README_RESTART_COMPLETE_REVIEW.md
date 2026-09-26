# Complete selected restart evidence review

`review_restart_complete.py` joins the independently qualified restart transport,
pair, viewport and resource readers for every pair in a stopped selected run.
It reconstructs the same admitted plan and split manifests as the frozen runner.
The exact baseline/selected-candidate O0/O1 population, ordered progress and
terminal receipts must match. Every pair must use a distinct application process
identity and two distinct native session paths. A shared evidence file must have
the same hash across readers and cells. All input and output bindings are checked
again before a success receipt is written. A late failure preserves partial
review evidence and cannot produce terminal success.

The new module leaves all earlier qualified readers and the runner unchanged.
It requires both viewport reviews, their separate source clocks and the common
resource owner/windows to agree with the freshly reconstructed transport pair.
Missing complete resource samples remain an explicit false coverage flag;
successful evidence review does not turn missing measurements into acceptance.

## Inputs, outputs and limits

Production inputs: `--run` is the private output of the qualified
`restart_application_runner.py`, after coordinator/application owners have exited.
Its selected plan must reconstruct from accepted upstream artifacts; a directory
containing generic READY_FOR_REVIEW results is insufficient. `--output` must be
fresh, private, separate from the immutable run and outside all its subdirectories.

Outputs: REVIEW_OWNER.json, ADMISSION.json, complete per-pair reviews under
`cells/`, and REVIEW.json or FAILED.json. REVIEW.json has status
`PASS_COMPLETE_SELECTED_RESTART_OBSERVATIONS_ONLY`. It reports exact population,
all evidence bindings, viewport/resource coverage and missing-measurement flags.
Full native caption semantics, timing/latency thresholds and functional restart
acceptance are still pending. Terminal lease evidence cannot establish full
historical lease/process coverage. No physical scanout, controlled hardware
qualification, CM5 capability or N4/N5 acceptance is inferred.

The guarded helper uses CPU14, BelowNormal priority and one math thread. It uses
the existing writer lock and checks campaign time, C:/G: free-space floors and
shared private allowance. Production review is bounded to one hour and 8 MiB of
new review output; crossing either bound fails while preserving the attempt.
No source, inference, GUI, microphone, playback or network/device session is
started by this reader. It is available for later execution after the actual
selected runs; no production run is claimed by development qualification.

The probe has 12 new cross-reader/driver checks and 12 unchanged population and
stopped-run checks. New fixtures are synthetic; leaf reader returns and payloads
are mocked in the population driver. The stopped-run tests use actual qualified
manifests but mock production plan admission. These checks do not execute a real
production review. All synthetic evidence and exact source snapshots stay private.

## PowerShell development checks

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\probe_restart_complete.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-complete-review-probe-v1'
```

## CMD development checks

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_complete.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-complete-review-probe-v1"
```

## Anaconda Prompt

Run the same CMD commands above with the explicit admitted interpreter. No
package installation or environment switch is needed. The probe requires the
current healthy D1 worker and a fresh output suffix. Direct unittest invocation
is unsupported because the probe supplies the private fixture roots and guards.

## Later production review

After an actual accepted-plan run finishes, substitute its verified directory
for RUN_DIRECTORY and a new private directory for REVIEW_DIRECTORY. These are
placeholders, not existing production evidence. Run from the N4 directory above.

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\review_restart_complete.py --run 'RUN_DIRECTORY' --output 'REVIEW_DIRECTORY'
```

CMD / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_restart_complete.py --run "RUN_DIRECTORY" --output "REVIEW_DIRECTORY"
```

Keep actual observations and nested reviews out of GitHub. Only code, this README,
and the development qualification binding belong in the worktree. The Pi remains
off throughout this campaign; its live integration checks await reconnection.
