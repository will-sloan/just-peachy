# Accepted main scoring summary

Purpose: render small aggregate tables from the independently reviewed 7,680-case
main modeled bank. Inputs are MAIN_MODELED_SCORING_ACCEPTANCE_V1.json and its
hash-bound private review/report. Output is a fresh Markdown file with 32
composition/tap cohorts, word-error denominators and 45 paired metric rows. No
audio, transcript, profile, actor or room identifiers are copied into the report.
No models, GUI, devices, capture, playback, enrollment or Pi connection are used.
The generator pins CPU14/BelowNormal and checks review authority, complete cohort
counts and rates against edit/word totals. It never overwrites an existing file.

This is an aggregate report, not a new metric run, stage acceptance or candidate
promotion. Unsupported metrics stay unavailable; target-only reference scope,
paired exclusions, small-cluster uncertainty and remaining GUI/resource/device
checks stay explicit. It does not change any source bound to a numerical plan.

PowerShell, from an existing shell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$stage='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$stage\summarize_main_scores_v1.py" --acceptance "$stage\MAIN_MODELED_SCORING_ACCEPTANCE_V1.json" --output "$stage\MAIN_MODELED_RESULTS_V1.md"
```

CMD or Anaconda Prompt, using the pinned interpreter without installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_STAGE=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_STAGE%\summarize_main_scores_v1.py" --acceptance "%JP_STAGE%\MAIN_MODELED_SCORING_ACCEPTANCE_V1.json" --output "%JP_STAGE%\MAIN_MODELED_RESULTS_V1.md"
```

Use a new output filename for a reproduction because the first result is retained.
The packaging reserve and deadline remain 2026-09-28 02:48:19 and 14:48:19 UTC.
