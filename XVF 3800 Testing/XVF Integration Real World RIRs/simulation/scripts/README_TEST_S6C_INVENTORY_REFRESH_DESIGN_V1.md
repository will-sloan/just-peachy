# Independent inventory refresh review V1

Purpose: verify all seven private discovery adaptations against complete original function ASTs, preserve the existing sentinel literal mapping, check unchanged original function bindings and test exact owned-root filtering on a tiny temporary tree. The test does not invoke collect(), construct actual refresh authority/specification or enumerate real campaign outputs.

Inputs: held refresh helper and pinned legacy source modules. The source receipt also binds the separately reproduced 46 owner fixtures. Outputs: a fresh REVIEW_RECEIPT.json with source hashes, named checks and explicit limits. No model, audio, raw log, prediction or actual runtime metadata is opened.

PowerShell:

~~~powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe" -B "$sim\scripts\test_s6c_inventory_refresh_design_v1.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\inventory_refresh_design_v1_reproduction"
~~~

Anaconda Prompt / Windows CMD (no activation required):

~~~bat
set "JP_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%JP_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" -B "%JP_SIM%\scripts\test_s6c_inventory_refresh_design_v1.py" --output "%JP_SIM%\reports\S6C\20260910T123540Z\independent_review\inventory_refresh_design_v1_reproduction"
~~~

Use a fresh output namespace. Source/fixture acceptance is separate from root's future post-closure census authorization. Actual refresh output must retain inherited failures, unverified owners and late-reference gaps; the outer refresh receipt must accompany its legacy and V7 inventories. No physical attempt count is derived from scores, index references or prepared namespaces.

