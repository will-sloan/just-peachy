# Narrow native correctness repair checks

Purpose: verify the repaired scorer's three independently reproduced faults while preserving the original21 fixtures and the reviewer's unchanged7 probes. These9 related checks cover declared frames and PCM SHA, exact audit authority and source/journal proofs, equivalent-output timing admission, changed endpoints/words/first hypotheses, impossible clock denominators, and one successful tiny synthetic matrix. The valid-input control creates a1second all-zero32kB PCM waveform plus matching synthetic journals and metadata. It calls only the existing pure evidence/scoring APIs; it starts no neural models, policy replay, actual native session, audio device or UI. It does not score actual study results or authorize production scoring.

Inputs: current reviewed scorer and pinned dependencies next to this helper, existing analysis Python with MeetEval0.4.3, and a fresh G output folder. Outputs: `TESTS.log`, exact-source `RECEIPT.json`, and explicitly synthetic input/audit/score metadata under `valid_synthetic_only`. Existing outputs and frozen source epochs are never overwritten. Current maintained scorer usage/admission is in `README_S6D_NATIVE_CORRECTNESS_V1.md`.

PowerShell:

```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6dAnalysis = "$s6dSim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $s6dAnalysis -B "$s6dSim\scripts\s6d_native_correctness_repair_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_correctness_v2\repair_checks_fresh'
```

Anaconda Prompt / CMD (no installation):

```bat
set "S6DSIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%S6DSIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" -B "%S6DSIM%\scripts\s6d_native_correctness_repair_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_correctness_v2\repair_checks_cmd_fresh"
```

Reruns must choose a new suffix. The independent7-probe script remains at `G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_correctness_independent_v1\reviewer_scorer_checks_v2.py`; run it with the same analysis interpreter, `--scripts` pointing to the current simulation scripts, and a fresh G `--output` folder. Its assertions and source must stay unchanged for repair review.
