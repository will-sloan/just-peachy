# S6D enrollment and continuous input plan helper

`s6d_enrollment_plan_v1.py` prepares an offline, reviewable INPUT PLAN for S6D pack sections7.3D/E and BXR9/BXR11. It never renders audio, runs neural models, uses the XVF device, invokes commands, or creates a capture ledger. Root reviews the plans before any separate builder or owner can execute them.

Inputs are the fixed S6C original A15/B15 galleries and tier15 template receipts, ECQ material manifest and Q occurrence lineage, S4.5 canonical240-scene microphone manifest, existing v1 RIR manifest, S6D hardware predeclaration, pacing audit, pack and current capture transport/owner source. Required expected SHA values are checked in code. Template/source/gallery files are resolved from these manifests; there are no audio-file globs. NumPy and SoundFile are the only nonstandard Python dependencies, available in the existing `.edge-speech-env`; no installation or model download is required.

The plan preserves complete E source clips at the nominal15s tier, actual original30-person membership, source-clean template bindings and E/C/Q separation. It selects two existing Library Conference Room paths, writes60 proposed microphone schedules, and plans two compatible900s continuous microphone sessions from36 original full canonical inputs plus declared zero gaps. It accounts for the capture transport's1s pre-roll,3s post-roll and16383/48000s maximum terminal callback allowance. The proposed unity input gain must pass future construction headroom checks; any change requires one common predeclared scalar, not per-file normalization. No payload is made here.

Outputs in a fresh directory are `DEVICE_ENROLLMENT_INPUT_PLAN_V1.json`, `CONTINUOUS_INPUT_PLAN_V1.json`, `BUDGET_FORECAST_V1.json`, `INPUT_PLAN_VALIDATION_V1.json`, `README.md`, and immutable helper/README copies under `source_epoch_v1`. JSON contains detailed identities, ordered utterances, transcripts, file/PCM hashes, header checks, geometry, missing-input flags, sample-offset schedules and forecast denominators. The validation receipt is a planning receipt and cannot stand for physical/model success.

PowerShell, from any directory:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& (Join-Path $repo '.edge-speech-env\python.exe') (Join-Path $sim 'scripts\s6d_enrollment_plan_v1.py') --output (Join-Path $sim 'reports\S6D\20260913T195357Z\device_enrollment')
```

Anaconda Prompt or ordinary CMD, from any directory:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_enrollment_plan_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\device_enrollment"
```

The output directory must not exist. For a reviewed rerun, choose a fresh sibling such as `device_enrollment_recheck_v1`; never overwrite published plans or delete evidence. The helper reads local source PCM only to verify format, exact hash and finite/peak properties; it does not synthesize candidate convolution audio. Run from the maintained helper under `simulation/scripts`; the copied source epoch is evidence, not a relocated standalone installation.

The command fails before publication if original hashes, gallery membership, source roles, tier durations, selected RIR geometry, continuous room compatibility or forecast limits disagree. The receipt records source checks and all output hashes. There are no inference fixtures because no inference is invoked. Independently review the produced schedules and readme before approving a future builder, especially same-source comparator extraction, proposed headroom policy, actual owner budget and current routing qualification. No current hardware consumption is inferred from the absence of a ledger.
