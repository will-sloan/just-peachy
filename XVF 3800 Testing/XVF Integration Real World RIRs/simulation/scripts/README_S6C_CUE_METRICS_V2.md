# Additive physical cue metric correction

`s6c_cue_metrics_v2.py` preserves the completed V1 audit and creates a separate
interpretation/matching correction. It reads only the V1 receipt and its240
bound case summaries. No raw telemetry, model, policy or hardware is rerun.

## Purpose, inputs and outputs

The V1 `host_receipt_age` statistic uses each interval's start age, weighted by
interval duration. V2 labels that scope explicitly; it is not an analytic
time-average age or continuous-time maximum. The original numbers remain.

V1 nearest-latest greedy matching can miss possible causal matches when two
references are near each other. V2 matches sorted detections to the earliest
eligible reference within the same predeclared0–1s lag, maximizing cardinality.
The detector predictions, reference events, angle thresholds, timing tolerance
and physical input population remain unchanged. This is evaluator-only scoring.

Input: `reports/S6C/20260910T123540Z/cue_audit_v1/PHYSICAL_CUE_AUDIT.json`
and all240 bound per-case JSON files.

Output: `reports/S6C/20260910T123540Z/cue_audit_v2/`
`PHYSICAL_CUE_METRIC_CORRECTION_V2.json` plus a short Markdown explanation.
The JSON binds code/README/source, six focused checks and corrected per-case/
aggregate counts. Existing correction output is never overwritten.

## PowerShell

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpMetric = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_cue_metrics_v2.py'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpMetric checks
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpMetric run
```

## Anaconda Prompt or CMD

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
set "JP_METRIC=%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_cue_metrics_v2.py"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_METRIC%" checks
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_METRIC%" run
```
