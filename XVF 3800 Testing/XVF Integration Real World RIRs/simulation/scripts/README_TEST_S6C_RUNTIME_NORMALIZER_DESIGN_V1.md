# Runtime normalizer independent review V1

Purpose: reproduce the held 36 metadata fixtures and independently check the two guard repairs, exact source delta, physical repetition/session distinction and B00 limited tail instrumentation. Inputs are pinned helper/README and preserved pre-repair source metadata. No actual normalization specification, completed runtime metadata, V7 collection, models, raw logs, audio or score table is read. The test never calls normalizer.run().

Outputs in a fresh directory: REPRODUCED_SOURCE_CHECKS.json and REVIEW_RECEIPT.json. Source hashes and scope limitations accompany the review. Use a fresh output suffix; existing results remain unchanged.

PowerShell:

~~~powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe" -B "$sim\scripts\test_s6c_runtime_normalizer_design_v1.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\runtime_normalizer_design_v1_reproduction"
~~~

Anaconda Prompt / Windows CMD (no activation required):

~~~bat
set "JP_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%JP_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" -B "%JP_SIM%\scripts\test_s6c_runtime_normalizer_design_v1.py" --output "%JP_SIM%\reports\S6C\20260910T123540Z\independent_review\runtime_normalizer_design_v1_reproduction"
~~~

This is a source/synthetic review, not authorization to normalize during a quiet interval. Later actual normalization still needs exact closed-run and observer bindings. B00's full journal/cursor proof is deliberately narrower than research dispatch/drain instrumentation. Final operating and scientific decisions remain with root and the separate final assembler.

