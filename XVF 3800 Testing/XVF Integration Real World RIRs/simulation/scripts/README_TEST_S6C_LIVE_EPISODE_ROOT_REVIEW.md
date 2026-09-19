# Independent live-name episode review

`test_s6c_live_episode_root_review.py` checks the additive name-episode helper
against a separate integer-sample oracle. It enumerates 6,250 combinations of
state sequences, source-support gaps and reference identities. It also executes
the held helper's pure fixtures and rejects invalid support. It does not load
models, score actual predictions or scan native logs.

Inputs: the exact SHA256 of the currently held `s6c_live_name_episodes.py` and a
fresh JSON output path. The oracle distinguishes assigned identity, undeclared
assignment and Unknown, ignores confirmation-only changes for episode splitting,
and checks every boundary, duration and end classification. It retains the
original V3 limitation that unresolved foreign names have no distinct metadata
identity. It does not certify empirical counts before the supplement executes.

Output: a review receipt with the exhaustive count, negative checks, actual pure
fixture results and exact source/README bindings. Existing receipts are never
overwritten. Replace the SHA below with the held SHA explicitly supplied by the
implementation owner; a source change requires a new review output name.

PowerShell:

```powershell
$s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cAnalysis = "$s6cSim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
$s6cHeldSha = '<exact held SHA256>'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cAnalysis "$s6cSim\scripts\test_s6c_live_episode_root_review.py" --held-sha $s6cHeldSha --output "$s6cSim\reports\S6C\20260910T123540Z\independent_review\LIVE_NAME_EPISODE_ROOT_REVIEW_V1.json"
```

Anaconda Prompt / CMD:

```bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_ANALYSIS=%S6C_SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
set "S6C_HELD_SHA=<exact held SHA256>"
set PYTHONDONTWRITEBYTECODE=1
"%S6C_ANALYSIS%" "%S6C_SIM%\scripts\test_s6c_live_episode_root_review.py" --held-sha "%S6C_HELD_SHA%" --output "%S6C_SIM%\reports\S6C\20260910T123540Z\independent_review\LIVE_NAME_EPISODE_ROOT_REVIEW_V1.json"
```
