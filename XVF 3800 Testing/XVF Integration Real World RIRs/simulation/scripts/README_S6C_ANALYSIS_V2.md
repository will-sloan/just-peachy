# S6C core analysis

`s6c_analysis_v2.py` scores completed, bound S6C predictions with the unchanged S6B/S6A text and anonymous-tracking metric functions. Primary word/CER, overlap MIMO, incomplete target-only text and strict-empty insertions stay separate. It retains first-final/latest/first-display-label final-word cp metrics, all source turns, missing waits, short-turn support, returns, fragmentation and lifecycle counters. Names in displayed labels may affect cp permutation costs; cpWER is not correct-name accuracy. A separate gallery-bound naming/exposure extension remains required.

The scorer reads actual gzip JSON predictions, the sealed historical 480-row input/support index and frozen 240-scene bank. It never passes truth to the runtime, loads audio/models or edits a prediction. Lexical counts use actual ASR-tap text; anonymous states, source support and embedding containment use the identity tap's known output mapping exactly once. Both taps share capture sample zero, but their source-to-output offsets remain distinct. Identity streams are explicit for split routing.

Index contract: `status`, unique `case_ids`, `profile_routes=[{candidate_id,stream,identity_tap}]`, and `rows=[{candidate_id,case_id,stream,identity_tap,status,result:{path,bytes,sha256}}]`. Each candidate and ASR tap must declare exactly one identity tap; separate route variants require separate candidate IDs, preventing aggregate denominator pooling. Fixed routes have one row per scene, rather than an invented second output. An index row may say COMPLETE_REUSED, but the bound payload must say COMPLETE. Payloads use the shared replay's real decisions/features/segmentation, three final-transcript label views and transcript events. A failed or absent output remains a failure/coverage row and never becomes empty ASR.

Inputs: explicit prediction index; immutable S6B INPUT_INDEX support bindings; canonical SCENE_MANIFEST; registered S6C design; exact existing metric code. Outputs below a new S6C report child: per-output score JSONs; compact scene/turn/population/short/strata/region/lifecycle/paired/cost/coverage tables; source bindings and ANALYSIS_RECEIPT. This core does not rank a winner, treat an exploratory bank as a holdout, infer word timestamps, or claim Pi performance. Attributions use the historical .75-second source-evidence expiry. Cost records deduplicate exact source bindings, never a recipe label alone.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_analysis_v2.py --test
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_analysis_v2.py --index 'epoch1\CHALLENGE_N00_PREDICTION_INDEX.json' --output-subdir 'n00_challenge_core_v1' --require-complete
```

Anaconda Prompt or Command Prompt (uses the preserved analysis interpreter with MeetEval0.4.3; no installation):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_analysis_v2.py --test
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_analysis_v2.py --index "epoch1\CHALLENGE_N00_PREDICTION_INDEX.json" --output-subdir "n00_challenge_core_v1" --require-complete
```

Relative indexes resolve under `reports/S6C/20260910T123540Z`; use the actual admitted epoch/index. `--limit 4 --no-bootstrap` permits a small adapter smoke in a separate output namespace. It cannot combine with `--require-complete`. The default paired uncertainty is 2,000 conditional within-room block resamples using inherited dependency handling, not independent population significance.

Completed aggregate namespaces are immutable. Interrupted scoring can reuse exact per-output analysis identities, with all dependencies rechecked; incomplete aggregate files require preserving the directory and using a fresh output child. Native cost-source identities are transitively bound by the verified prediction; this scorer does not reopen every native receipt. Do not change this scorer or its metric dependencies during a run. A core COMPLETE_REQUESTED_INDEX means only the exact declared grid was scored; full240 confirmation is listed per route, and gallery identification/exposure remains explicitly outside core completion.


## V2 registry admission and preserved V1

This separate version preserves the original scorer and its completed N00/smoke results. It binds all 184 registered labels from the original 153-label design, seven C-only calibration candidates and 24 outcome-informed admission/family rescue candidates. Exact original parent-design bindings, unique IDs and known comparison parents are required. These are registered labels, not a claim of 184 unique effective settings or executed candidates. Paired comparisons use the declared parents only when both outputs are present. The rescue amendment follows N00 findings and inspected N01 functional smoke; it is not pristine preregistration.

V2 also validates the canonical prediction identity digest for both native and policy prediction schemas. Per-output metric definitions remain unchanged. New code/schema identities prevent silent reuse of V1 scores. The original V1 source is itself included among V2 dependencies. The separate naming scorer continues to use frozen V1 source helpers; it does not depend on V2 aggregate registry behavior.
