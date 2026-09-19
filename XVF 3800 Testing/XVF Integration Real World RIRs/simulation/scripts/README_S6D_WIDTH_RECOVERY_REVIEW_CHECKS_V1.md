# Independent width aggregate recovery checks

Purpose: test exact one-hop process identity validation, nonfinite creation-time rejection, health-time PID reuse and launcher exit, and unchanged original aggregate API wiring. These7 bounded checks use synthetic process records and AST comparisons of actual helper/source functions. They do not launch subprocesses, call scientific scoring/aggregation, instantiate models, access devices, or create UI. Root must separately qualify actual host launcher topology and admit an exact production queue.

Inputs: frozen recovery helper, original hash-reviewed score adapter, and fresh G output directory. Outputs: `TESTS.log` and exact-source `RECEIPT.json`. Original source/results remain immutable. First epoch `e8dfcf45…` is expected to fail the two NaN admission cases; repaired epochs must pass the same assertions. The existing21 author ownership/STOP fixtures are independently rerun separately under their maintained recovery README. No wide score matrix is constructed or rescored.

PowerShell:

```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6dRecovery = "$s6dSim\reports\S6D\20260913T195357Z\runner\width_score_recovery_preparation_v1"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s6dSim\scripts\s6d_width_recovery_review_checks_v1.py" --helper "$s6dRecovery\s6d_width_score_recovery_v1.py" --adapter "$s6dSim\scripts\s6d_angle_width_score.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\width_recovery_independent_v1\adverse_fresh'
```

Anaconda Prompt / CMD:

```bat
set "S6DSIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6DRECOVERY=%S6DSIM%\reports\S6D\20260913T195357Z\runner\width_score_recovery_preparation_v1"
"C:\Users\amiri\anaconda3\python.exe" -B "%S6DSIM%\scripts\s6d_width_recovery_review_checks_v1.py" --helper "%S6DRECOVERY%\s6d_width_score_recovery_v1.py" --adapter "%S6DSIM%\scripts\s6d_angle_width_score.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\width_recovery_independent_v1\adverse_cmd_fresh"
```

For later exact epochs change only the helper path and use a new output suffix. No environment installation is needed.
