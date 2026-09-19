# Native N07 cadence and released-state audit

This bounded, model-free audit reads336 completed epoch2 native cells: C065 fixed N01, C071 uncertainty cue-off and C082 uncertainty plus real cues, each56 scenes and both taps. It does not infer, rescore, launch hardware, alter an old artifact or export vectors/audio. Exact completed core→prediction index→native source index→receipt→event bytes and summaries are verified. Each event file is streamed once and the bytes hashed are the bytes parsed. Bulk waveform/model/vector payloads remain transitively bound and are not reopened.

Inputs are the three exact completed core receipts, their native source indexes, frozen epoch2 digest, events and native summaries. `prepare` creates cadence_audit_v1/PLAN.json without scanning native logs. `run` requires its exact SHA256 and produces NATIVE_CELLS.json with only counts/scalars/small representative diagnostics, plus RESULT.json with per-candidate/tap totals and all source bindings. Existing output is preserved.

The audit separates role opportunities from shared source dispatches; admitted roles from actual model calls; due debt records from an identified target chosen. The implementation acknowledges every due ledger entry on a global admitted window, so this does not prove that a specific person's debt received their voice. Cue/onset/cosine causes are not fully separate in the logs; sole-cue causal admissions remain null. Logged context age is source cursor minus the newest released snapshot timestamp among returned context rows; it does not measure the age of every track. Actual scheduler maximum pending count is distinct from journal backlog and final lag. Missing peak journal lag remains null. Nested model/API/full-dispatch times must not be added, and accelerated batch measurements are not paced latency or CM5 timing.

PowerShell:

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe'
& $s6cPython "$s6cScripts\s6c_native_cadence_audit.py" tests
& $s6cPython "$s6cScripts\s6c_native_cadence_audit.py" prepare
# Substitute the exact SHA256 printed by prepare; do not approve a changed plan.
& $s6cPython "$s6cScripts\s6c_native_cadence_audit.py" run --plan 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\cadence_audit_v1\PLAN.json' --sha256 PLAN_SHA256
```

Anaconda Prompt / CMD:

```bat
set "S6C_SCRIPTS=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set "S6C_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%S6C_PYTHON%" "%S6C_SCRIPTS%\s6c_native_cadence_audit.py" tests
"%S6C_PYTHON%" "%S6C_SCRIPTS%\s6c_native_cadence_audit.py" prepare
"%S6C_PYTHON%" "%S6C_SCRIPTS%\s6c_native_cadence_audit.py" run --plan "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\cadence_audit_v1\PLAN.json" --sha256 PLAN_SHA256
```

Use one audit worker and keep it outside a paced quiet interval. No installation is required. Tests exercise duplicate/invalid admissions, released-context causality, name-schedule rejection, exact stream parsing/hash rejection, malformed JSON, unadmitted model output and same-length changed byte rejection without native/model work.
