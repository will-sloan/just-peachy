# S6B factual component screen

`s6b_component_screen.py` creates a compact, reviewable profile/tap table from completed core, revision and cp-uncertainty analysis. It performs no inference, policy replay, outcome-based tuning or automatic candidate ranking. A human-readable admission rationale is a separate review document.

## Inputs and outputs

The selected report root must contain the effective profile registry and matching completed analysis directories. All three receipts must have the same prediction-index identity. Inputs are pooled profile metrics, all complete-reference short-turn results, revision/exposure summaries and deduplicated upstream recipe costs.

The output directory contains `COMPONENT_SCREEN.csv`, `COMPONENT_SCREEN.json` and `COMPONENT_SCREEN_RECEIPT.json`. Each row is one profile/tap with separate primary words/CER, overlap MIMO, incomplete target-only and empty insertions; three cp label views; unknown/mixed and return counts; subsecond and 1–<2-second evidence/presence/correctness; revision harm/exposure; and actual named recipe work. Source hashes and the index are preserved in the receipt.

Full-engine CPU and nested segmentation/embedding/ASR phases overlap and must not be added. Accelerated elapsed sums are not paced device latency. The same upstream recipe cost appears beside every profile that reuses it for comparison; summing those repeated costs would overcount campaign work. Historical B00 costs remain unavailable. Actual replay policy time is separate from measured native recipe work. Resource qualification still requires paced finalist measurements.

Subsecond correctness uses the ambiguity-aware duration mapping and keeps all missing/unknown examples. Exposure measures retained-row modeled state, not aligned word errors or physical GUI visibility. The table does not establish an independent validation set, isolate bundled comparisons, or replace the matched interaction and dependency contracts.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$python = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $python "$sim\scripts\s6b_component_screen.py" --analysis-subdir challenge_analysis_v1 --revision-subdir challenge_revision_v1 --cp-subdir challenge_cp_uncertainty_v1 --output-subdir component_screen_v1
```

To summarize another complete index, supply its three corresponding analysis subdirectories and a new output subdirectory. Optional `--report` changes the report root.

## Anaconda Prompt or Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "ANALYSIS_PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_component_screen.py" --analysis-subdir challenge_analysis_v1 --revision-subdir challenge_revision_v1 --cp-subdir challenge_cp_uncertainty_v1 --output-subdir component_screen_v1
```

Reuse the existing analysis environment; no installation is needed. Run only after the three source analyses finish. For the already completed R0 diagnostic, use `r0_challenge_analysis_v1`, `r0_challenge_revision_v2`, `r0_cp_uncertainty_v1` and a distinct `r0_component_screen_v1` output directory. R0 alone does not support component-family selection.

