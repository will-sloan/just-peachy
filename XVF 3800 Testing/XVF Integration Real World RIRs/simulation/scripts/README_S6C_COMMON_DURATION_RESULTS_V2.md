# Full-bank common-roster duration comparison V2

This separate model-free collector consumes the completed six-profile common-roster core and naming analyses for all240 scenes, both taps and777 source occurrences per route. It preserves V1's panel helper/results and its paired exposure, within-person, corpus and censored-delay formulas. V2 fixes the prospective V1 read/hash race: the exact table buffer whose bytes/hash are verified is the buffer parsed. It does not infer, rescore, create galleries or change an old result.

Required inputs are complete core and naming receipts for the exact same2,880-output index, candidate IDs C141–C146, A/B common30 rosters at5/15/30 seconds, plus their exact source-bound TURNS/RETAINED_ROWS tables. Every777 occurrence and all unavailable/withheld/unknown states remain per route. Outputs in a fresh report child are TIER_PROFILE_RESULTS, CORPUS_TIER_RESULTS, WITHIN_PERSON_TIER_DELTA, POOLED_TIER_DELTA, PAIRED_NAME_DELAY_RESULTS, RETAINED_ROW_EXPOSURE and DURATION_RESULTS_RECEIPT. These are descriptive development confirmation, not a new holdout or inferential confidence interval.

PowerShell (run only after both full source analyses complete):

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe'
& $s6cPython "$s6cScripts\s6c_common_duration_results_v2.py" --test
& $s6cPython "$s6cScripts\s6c_common_duration_results_v2.py" --core-subdir full_n01_common_duration_core_v3 --names-subdir full_n01_common_duration_names_v3 --output-subdir full_common_duration_results_v2
```

Anaconda Prompt / CMD:

```bat
set "S6C_SCRIPTS=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set "S6C_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%S6C_PYTHON%" "%S6C_SCRIPTS%\s6c_common_duration_results_v2.py" --test
"%S6C_PYTHON%" "%S6C_SCRIPTS%\s6c_common_duration_results_v2.py" --core-subdir full_n01_common_duration_core_v3 --names-subdir full_n01_common_duration_names_v3 --output-subdir full_common_duration_results_v2
```

The source names above are planned completed-analysis namespaces, not a claim they already exist. No package installation is required. Existing output cannot be overwritten. Conditional paired waits only include both-observed cases, with left-only/right-only/neither counts retained; zero retained-row wrong exposure must not be substituted for live wrong-name speech samples. Fixed-roster tier changes also change enrollment speech/centroid content, so they are not a pure duration-only physical intervention.
