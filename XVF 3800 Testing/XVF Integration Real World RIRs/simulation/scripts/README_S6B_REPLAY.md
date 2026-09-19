# Exact causal tracker replay

`s6b_replay.py` feeds actual cached neural observations into the same frozen application tracker and incremental scheduler used by native runs. It delivers only events whose required samples and measured upstream compute have arrived; equal-time ordering and expiry are shared across policies. This is modeled causal availability, not measured device latency. Historical B00 retains its exact original labels and timing as a separately identified control.

Inputs: frozen epoch, effective profile registry, complete per-recipe neural receipts, accepted sanitized cues. It never supplies room, person, source truth, transcripts of references or future samples to a prediction module. Outputs: per-profile first-final/latest/first-display-label predictions, forward revision events, evidence diagnostics, and a prediction index. It performs no new neural inference or hardware operation.

PowerShell:

```powershell
$s6bSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:JP_S6B_SIM = $s6bSim
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s6bSim\staging\s6b\20260909T230840Z\epoch2\scripts\s6b_replay.py" --epoch epoch2 --panel challenge
```

Anaconda Prompt / CMD:

```bat
set "JP_S6B_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6B_SIM%\staging\s6b\20260909T230840Z\epoch2\scripts\s6b_replay.py" --epoch epoch2 --panel challenge
```

After explicitly retaining general candidates, use `--panel all --profiles B01 B05 ...` with exact registry IDs. `--index-name NAME.json` selects a separate report index for diagnostic runs. Existing prediction files require the exact same profile/neural/source identity; code changes need a named new epoch. Word sequences are checked unchanged by label revision. First-display-label diagnostics use the final lexical text attributed to the initial nonempty display label, distinct from first-final and latest-revised cpWER.

Before extending or resuming a completed prediction set, run the completed-index byte guard documented in `README_S6B_PREDICTION_GUARD.md`. It validates existing prediction bytes against previously bound output digests, in addition to the frozen replay's native-artifact and prediction-identity checks. Unindexed incomplete replay outputs require diagnosis. The authoritative epoch is2; epoch1 was never executed. Default CLI arguments still exist for development, so use the explicit epoch shown above.
