# Complete source admission for metadata probes

The first guarded reader probe stopped before its tests because its primary
`code` field contained the 120-file resource family but omitted the new entry
script. The 213-file reader list appeared only in `reader_code`, which the live
census correctly did not use as execution authority. The failed V1 attempt and
its sources remain immutable. The original planner V1 probe has the same wiring
and must not be dispatched.

`guarded_metadata_probe_v1.py` creates a distinct metadata-only envelope with
the complete producer code in `code`, including the exact running script and
all unchanged resource dependencies. It does not edit the original guard or
relax command, identity, allocation, disk, deadline, supervision or census checks.
It permits only the named reader/planner V2 diagnostic entries. Source lists
are bounded, deduplicated with conflict rejection, and never truncated.

Inputs: the original modes plan, the unchanged reader/planner code manifests,
and the two actual closed independent score reviews. Outputs: a fresh private
ADMISSION, EXECUTION_PLAN, source snapshots, tests, initial/final resource checks
and RESULT or FAILED. The reader V2 runs 7 manifest tests plus its original 11
tests and actual pair check. The planner V2 runs the same 7 manifest tests plus
its original 10 tests and 1,240 V4 payload comparisons. It does not create a
production application plan, load models, start a GUI or access devices.

Each V2 probe must be dispatched via `supervisor.start` after exact prior-owner
closure and a fresh complete resource census. Use the existing CPU14,
BelowNormal, one math thread, GPU-off policy, 8 MiB and 20 minutes. The resource
guard continues to require sole N4 allocation and preserve C50/G75-GiB floors,
50-GiB allowance and the unchanged packaging reserve. Review full source,
resource and exact supervisor/probe closure evidence before accepting a result.

PowerShell underlying argv (for a supervised spec, not a duplicate worker):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPython -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_panel_scoring_guarded_v2.py --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-plan-v3.json --main-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-main-score-review-v3-timeout120-v1/RESULT.json --modes-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-score-review-guarded-v1/RESULT.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/panel-scoring-guarded-probe-v2
```

CMD/Anaconda Prompt use the existing interpreter without environment changes:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_panel_scoring_guarded_v2.py --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-plan-v3.json --main-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-main-score-review-v3-timeout120-v1/RESULT.json --modes-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-score-review-guarded-v1/RESULT.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/panel-scoring-guarded-probe-v2
```

After a passing real-pair reader result and closure, the planner command replaces
the script with `probe_paced_panel_plan_guarded_v2.py` and the output with
`panel-planner-guarded-probe-v2`. All other arguments are identical. Preserve
each failed attempt; subsequent changes require a fresh derivative/output.

Standalone manifest tests, only in an available metadata slot:
PowerShell: `& $jpPython -B research/nvidia_nemo_comparison/20260924_campaign/n4/test_guarded_metadata_probe_v1.py -v`.
CMD/Anaconda: the same quoted interpreter followed by `-B`, that test path and
`-v`. These in-memory tests require no audio, filesystem writes or numerical
worker, and do not establish runtime/resource qualification by themselves.

The original reader and planner READMEs describe the unchanged numerical and
payload semantics. V2 results additionally bind `producer_code`, their metadata
envelope and the seven admission regressions. No N4/N5 acceptance or live CM5
claim follows from a diagnostic pass; the Pi remains off.
