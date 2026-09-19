# S6D frozen-v3 pilot analysis

Purpose: `s6d_application_pilot_analysis.py` analyzes all12 predeclared v3 cells and compares original/delivery-only/delivery+repair variants plus naming over the C065 anonymous parent. It never starts a model, source, device, or supervisor and never fabricates missing outputs. It is bound to manifest SHA256 `ec110adcbaf230c5f33b49629967e163f5d526b7a339123c05fb000a14d7138f`.

Inputs: the exact frozen manifest, its declared cell output paths, semantic RESULT receipts, actual event consumer/journal JSONL, current final transcript JSONL, finalization receipts, and resources. Output must be a fresh directory. Outputs: PLAN.json records clocks/conventions/goals before reading cell outputs; RESULT.json includes every missing/failed cell, actual first-text timing, never-emitted finals, identities/revisions/unnamed counts, raw words in paired rows, paired delay differences, startup and resource/queue summaries. No source truth is used by this analyzer; it does not calculate cpWER or naming accuracy.

Actual publication and event consumption share each process's monotonic clock and are normalized by its own actual `source_started` publication. The waveform reader appends each0.1s block before sleeping, so publication minus source-end is allowed to be negative by approximately0.1s. This is an explicitly reported source-block convention, not measured physical latency. Startup asset checks/model loads are separately reported; no warmup is invented or subtracted. Stable utterance IDs are paired only with matching source starts; endpoint or word changes remain adverse. The predeclared p50<=0.10s and p95<=0.25s added naming delay are diagnostic goals with p99 and never emitted retained, not qualification from a few samples. No known profile is an unnamed row, which includes correctly anonymous C065; it is not automatically an error.

PowerShell (use another fresh output suffix if occupied):
```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_pilot_analysis.py" --manifest "$s6dSim\reports\S6D\20260913T195357Z\application\native_pilot_v3\MANIFEST.json" --output "$s6dSim\reports\S6D\20260913T195357Z\application\native_pilot_analysis_v1"
```
Anaconda Prompt / Windows CMD (no activation needed):
```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_pilot_analysis.py" --manifest "%S6D_SIM%\reports\S6D\20260913T195357Z\application\native_pilot_v3\MANIFEST.json" --output "%S6D_SIM%\reports\S6D\20260913T195357Z\application\native_pilot_analysis_v1"
```

`native_pilot_analysis_prelaunch_v1` is a bounded schema/missing-evidence check only. A PARTIAL_MISSING_EVIDENCE result before production is expected and must never be described as a successful native pilot. Frozen source and failed outputs remain unchanged. GUI, physical, CM5, full-bank, balanced paced repeats and long sessions are separate capabilities.

Model-free verification: `s6d_application_pilot_analysis_checks.py` creates temporary synthetic event/receipt files, exercises the actual nested journal schema and source-start clock arithmetic, preserves unavailable cells and mismatched raw words, rejects an undrained consumer, and refuses timing alignment across different source starts. These temporary fixtures are explicitly synthetic and provide no native result. Output is unittest stdout; temporary files are cleaned automatically.

PowerShell:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_pilot_analysis_checks.py"
```
Anaconda Prompt / CMD:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_pilot_analysis_checks.py"
```
