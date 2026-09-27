# Aggregate modes scoring summary

`summarize_modes_scores_v1.ps1` publishes the 128 aggregate composition/mode/tap
rows from the independently reviewed 1,536-case modes panel. It verifies the
acceptance, review, scoring terminal and report hash joins, the exact cohort
census, complete execution/metric counts, and error/word rate algebra. It does
not recompute metrics, read audio, start models, enumerate devices or launch a
GUI. Naming, resource, hardware and application acceptance remain unavailable.

Inputs: `MODES_MODELED_SCORING_ACCEPTANCE_V1.json` and its hash-bound private
review, scoring terminal and aggregate report. Output: a fresh UTF-8 Markdown
summary, at most 64 KiB, with aggregate counts and provenance hashes only. Existing
outputs are never overwritten. No per-scene text, profile or audio is published.

The script uses installed PowerShell 7, CPU14 and BelowNormal priority. It has
no model allocation and may run as independent report work while a numerical
worker runs. Keep that worker's frozen sources unchanged. Run from the campaign
worktree and preserve the generated report and console receipt. This summary is
not an independent acceptance test; the completed score review is its input.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPwsh='C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
& $jpPwsh -NoProfile -File research/nvidia_nemo_comparison/20260924_campaign/n4/summarize_modes_scores_v1.ps1 -Acceptance research/nvidia_nemo_comparison/20260924_campaign/n4/MODES_MODELED_SCORING_ACCEPTANCE_V1.json -Output research/nvidia_nemo_comparison/20260924_campaign/n4/MODES_MODELED_RESULTS_V1.md
```

CMD or Anaconda Prompt (no environment changes):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe" -NoProfile -File research/nvidia_nemo_comparison/20260924_campaign/n4/summarize_modes_scores_v1.ps1 -Acceptance research/nvidia_nemo_comparison/20260924_campaign/n4/MODES_MODELED_SCORING_ACCEPTANCE_V1.json -Output research/nvidia_nemo_comparison/20260924_campaign/n4/MODES_MODELED_RESULTS_V1.md
```

After the first run, reproduce into a different private output path and compare
SHA-256 hashes. A missing, changed or incomplete input must stop publication.
Do not reinterpret mode differences as identity accuracy or use this report to
claim N4/N5 completion. Packaging cutoff and campaign deadline are unchanged;
the Pi remains off.
