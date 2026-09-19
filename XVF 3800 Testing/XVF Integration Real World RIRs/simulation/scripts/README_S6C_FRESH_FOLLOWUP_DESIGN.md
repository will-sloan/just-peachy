# Register bounded followups on fresh N01 evidence

`s6c_fresh_followup_design.py` adds 44 explicit configurations (C147–C190)
to V4, for 234 total labels including the 44 preserved S6B controls:

- C147–C166: three existing null seeds and nominal-geometry diagnostics for
  normalized, reliability, hypothesis, semi-Markov and bounded-global parents.
- C167–C182: all eight fresh families, cues off/real, changing only commitment
  duration from 1.0 to 0.75 seconds; two disjoint observations remain required.
- C183–C190: normalized cues off/real at capacities 16, 32, 128 and 256,
  with current 64-track parents and otherwise identical lifecycle/evidence.

Inputs: immutable V4 registry, original design and rescue definitions, completed
motivating analysis receipts, and the previously frozen cue-variant index. The
helper compiles the actual v3 profile API, checks every exact parent delta and
preserves all prior profile rows. Outputs are a new registration amendment,
88 profile files and `EFFECTIVE_PROFILE_REGISTRY_V5.json`. It performs no neural
inference, policy replay or scoring. A future epoch must bind this registry.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:JP_S6C_SIM = $s6cSimulation
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s6cSimulation\scripts\s6c_fresh_followup_design.py"
```

Anaconda Prompt / CMD:

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6C_SIM%\scripts\s6c_fresh_followup_design.py"
```

These are outcome-informed, exploratory followups. The two commitment values
do not establish a validated operating range. Quarantine/shadow retain their
additional gates, so a failed duration rescue cannot reject the mechanisms.
Nominal geometry is an explicit diagnostic using reference angles; it is never
deployable sensor evidence. No reference person IDs, text or boundaries enter
ordinary predictors. All 240 scenes remain eligible, with all-240 confirmation
and native/paced acceptance still required for retained broad recommendations.

Exact reruns preserve registration timestamps and compare immutable contents.
Changed definitions require a new version. Rollback selects an earlier registry
for a future epoch; never replace existing results, profiles or active sources.
The six remaining configuration slots are deliberately unfilled.
