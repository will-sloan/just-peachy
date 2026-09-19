# Independent completed enrollment-duration arithmetic

`test_s6c_common_duration_review.py` reads the exact completed collector receipt
and independently recomputes support/name partitions, pooled tier deltas,
observed/censored paired wait counts and percentiles, and separate retained
transcript row exposure. It hashes each exact byte buffer before parsing it.
It verifies actual fixed gallery counts from the evaluator-only map. It does
not run models, rescore predictions, edit completed results or infer accuracy
from gallery metadata. Within-person/corpus table bytes are bound; the detailed
independent arithmetic checks focus on the pooled/profile/delay/exposure tables.

Inputs: pinned completed common-duration receipt, original completed core/name
receipts/tables, exact gallery extension, pinned analysis interpreter. Output:
one fresh source-bound independent review JSON. No earlier receipt is replaced.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$s6cSimulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "$s6cSimulation\scripts\test_s6c_common_duration_review.py" --output "$s6cSimulation\reports\S6C\20260910T123540Z\independent_review\COMMON_DURATION_COMPONENT_REVIEW_V1.json"
```

Anaconda Prompt / CMD:

```bat
set "S6C_SIMULATION=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set PYTHONDONTWRITEBYTECODE=1
"%S6C_SIMULATION%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%S6C_SIMULATION%\scripts\test_s6c_common_duration_review.py" --output "%S6C_SIMULATION%\reports\S6C\20260910T123540Z\independent_review\COMMON_DURATION_COMPONENT_REVIEW_V1.json"
```
