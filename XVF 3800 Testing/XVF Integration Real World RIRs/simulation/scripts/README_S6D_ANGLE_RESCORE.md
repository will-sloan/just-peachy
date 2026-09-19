# S6D evaluator-only manual-bearing sensitivity

Purpose: rescore the same 240 accepted physical telemetry traces at hypothetical manual reference half-widths 5, 2 and 0 degrees. Original acquisition metadata remains at ±5 degrees. No audio is played, regenerated, perturbed or normalized; no predictor, neural model, hardware or production application is invoked.

Inputs: immutable S6C `cue_audit_v1` and V2 authority plus review, their bound accepted raw telemetry and S6A callback-quantized source supports; C065/C079/C088/C091 all240/both-tap frozen predictions and core scores, plus A15/B15 naming scores. Sources are resolved from existing indexes, never from a recursive audio glob. The source and README are hashed before execution. NumPy is preloaded solely to avoid a historical telemetry-helper ABI-path conflict.

Outputs under a fresh `--output`: `PLAN.json`, per-case local JSON, `RESULT.json`, `STREAM_SUMMARY.csv`, `TURN_RESCORES.csv`, `PAIR_RESCORES.csv`, `PAIR_SUMMARY.csv`, `ACQUISITION_CENSORING.csv`, `ACQUISITION_SUMMARY.csv`, `INTERVAL_DEPENDENT_POPULATION.csv`, `PREDICTION_INVARIANCE_BINDINGS.json`. These contain exact sources, case/turn/time-support denominators, scores, censoring, invariance receipts and limitations. Large per-case/prediction bindings stay local for the compact handoff.

The primary turn metric reproduces S6C exactly-one-active-source support. It differs from sole-person support when several same-person source intervals overlap. Native observations are linear 0..180; endpoints remain distinct. Whole signed manual intervals are folded at ±90 and wrapped, using the preserved geometry helper. Nominal sector scoring stays fixed. Allowed-sector matching and interval-dependent strict-sector eligibility are separate sensitivity diagnostics. All threshold occupancy reports carry both valid-support and full-support denominators. Thresholds 0/5/10/20/35 are descriptive tolerances, not runtime triggers.

First/sustained acquisition reuses verified original S4 nominal-sector results for the original per-source envelope population, including limited-overlap cases, invalid gaps and censored observations. Because nominal sectors do not change, these values are identical across all three overlays. This does not invent interval-specific timing or a device reaction latency. Same-person stability and pair separation use observed turn means and retain reference identity/position strictly in the evaluator. They do not associate a beam with a recognized voice.

Prediction invariance checks all240/both taps for four specified controls. It hashes frozen prediction bytes, full decompressed predictions and full score files before/after, then verifies the evaluator wrapper varies only its separately named half-width. This proves a fixed evaluator dependency graph and immutable inputs, not deterministic ASR/identity results under a new native run. No upstream rerun is claimed.

Use the existing interpreter; no installation or activation is needed. Start from any directory. Choose a new output suffix for a completed rerun. `run` can resume an incomplete output only when the source/README/plan and completed per-case bindings still verify; it never overwrites completed output files. An unexpected failure stays on disk for diagnosis. The finite single-process helper prints progress every20 traces and exits; it installs no automation.

PowerShell:

```powershell
$s6dRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6dSim = Join-Path $s6dRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6dPython = Join-Path $s6dRepo '.edge-speech-env\python.exe'
$s6dAngle = Join-Path $s6dSim 'scripts\s6d_angle_rescore.py'
$s6dOut = Join-Path $s6dSim 'reports\S6D\20260913T195357Z\angles\eval_v1'
& $s6dPython -B $s6dAngle checks
& $s6dPython -B $s6dAngle run --output $s6dOut
```

Anaconda Prompt or Windows CMD:

```bat
set "S6D_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6D_SIM=%S6D_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6D_PYTHON=%S6D_REPO%\.edge-speech-env\python.exe"
set "S6D_ANGLE=%S6D_SIM%\scripts\s6d_angle_rescore.py"
set "S6D_OUT=%S6D_SIM%\reports\S6D\20260913T195357Z\angles\eval_v1"
"%S6D_PYTHON%" -B "%S6D_ANGLE%" checks
"%S6D_PYTHON%" -B "%S6D_ANGLE%" run --output "%S6D_OUT%"
```

`checks` runs analytic wrap/fold/endfire/sector controls and3000 seeded property draws. The first analytic check exposed floating-point `acos/sin` roundoff at the exact +30 lab /120 native sector boundary. The supplemental allowed-interval-sector calculation snaps interval bounds within1e-9 degrees of exact sector boundaries. Historical nominal-sector scoring is preserved unchanged. `freeze --output <fresh path>` can separately create the plan before a later `run`. CPU/disk work is read-only on old evidence. Only the requested new report directory is written.
