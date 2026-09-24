# Scoring saved Controller evidence

`score_controller.py` reads an immutable Controller RESULT_INDEX, its ADMISSION,
completed checkpoints, audio-only manifest and evaluator-only truth. It checks
bindings and produces a new SCORES.json without touching run evidence. Missing
and failed rows remain in counts. D0's missing full track activity stays
unavailable. D1 probability frames are intersected with delivered waveform
support; raw timestamps/probabilities remain unchanged and overhang is reported.
Raw words must match speaker segments after declared normalization. This is an
evaluator, never a new integrated inference run.

Run after the owning numerical workers finish, from the worktree. PowerShell:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\score_controller.py --index 'G:\Just_Peachy_N1\20260924_campaign\local\n2\factorial-v2\D1_E0\RESULT_INDEX.json' --manifest 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\AUDIO_ONLY.json' --truth 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\EVALUATOR_TRUTH.json' --scope 'N2 screen rescore, not N4 full bank' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\rescore-n2-d1e0-v1'
```

CMD/Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\score_controller.py --index G:\Just_Peachy_N1\20260924_campaign\local\n2\factorial-v2\D1_E0\RESULT_INDEX.json --manifest G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\AUDIO_ONLY.json --truth G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\EVALUATOR_TRUTH.json --scope "N2 screen rescore, not N4 full bank" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\rescore-n2-d1e0-v1
```

All five arguments are required; output must be fresh. Scope identifies the real
experiment. A 96-cell N2 screen cannot count as N4's 480-cell bank. CPU4/BelowNormal
limits this process. Library pins/tests are in README_METRICS.md. Name display
timing and whole-GUI resources are separate qualifications.

`coverage.py` takes intended profile/job IDs and execution rows. Missing rows are
NOT_TESTED. COMPLETE requires a binding; FAILED/INCOMPATIBLE require reasons. It
counts, but does not certify a binding or infer compatibility. `paired.py` takes
matched integer error/word counts and dependency groups; outputs pooled deltas,
cluster-bootstrap intervals and leave-room/actor/family-out sensitivities.
Both are exercised by `test_n4.py` using the README_METRICS.md test command.

`smoke_scoring.py` evaluates only the lexicographically first completed cell from
each complete N2 D0/E0 and D1/E0 screen, using the exact original raw words and
activity events. Inputs default to the private campaign root (`--local` override).
Output is a small redacted two-cell conformance receipt, not new N4 inference or
a quality ranking. Both upstream batches must already have all 96 cells.

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\smoke_scoring.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\scoring-smoke-v1.json'
```

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\smoke_scoring.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\scoring-smoke-v1.json
```
