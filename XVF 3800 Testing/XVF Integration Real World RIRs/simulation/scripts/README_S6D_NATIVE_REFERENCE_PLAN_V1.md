# S6D continuous reference input preparation V1

`s6d_native_reference_plan_v1.py` prepares an evaluator-only reference projection for the exact existing O0 38-piece,29,238,826-frame S6C composition proposed for two independent S6D host sessions. It reads original Q occurrence identity/text, original saved support, exact input index, canonical scene metadata and composition offsets. It calls the unchanged hash-pinned `s6a_support_metrics.py` pure interval/support-validation APIs. No scorer, policy, model, audio, device or GUI execution occurs. No RIR or waveform is created.

The existing support already includes its RIR convention. Apply its saved output offset once, clip each interval to that actual capture length, then add the exact composition start sample. The new guard's tested shift function preserves repeated occurrences, missing alignment and incomplete-reference flags. Metadata identities remain corpus-qualified; local A/B cast letters are never merged across scenes as a person. Full-session all-speaker WER is ineligible if any included source has incomplete/disallowed reference. The projection does not manufacture word times or pretend an original canonical single-scene scorer accepts a continuous session.

Inputs are `--sim` pointing to the simulation directory and `--output` pointing to a fresh G directory. Exact source hashes are pinned in the helper. JSON and existing support hashes, denominator480input rows/240scenes/777Q occurrences, each composition source binding/frame count and Q occurrence/source/person identity must agree. Outputs: `HOST_REFERENCE_INPUTS.json` with source bindings,38piece records and shifted occurrences, and compact `REFERENCE_PREPARATION_RECEIPT.json`. This is input preparation, not completed scoring. No output is passed to the predictor.

For a confirmation cell, add `--case-id S45_08_07 --tap O0` (or its exact O1 source). This emits the same evaluator schema with one whole admitted piece at frame0 and no inserted gap. With no case ID it uses the exact38-piece composition and selected existing tap. The output now includes `input_audio`, `source_tap` and `source_case_id` so the scorer can require an exact match to the runtime source. Earlier reference_v1 artifacts remain unchanged; prepare a fresh namespace with these explicit source fields for future scoring. No source WAV is read by this metadata helper.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" -B "$sim\scripts\s6d_native_reference_plan_v1.py" --sim $sim --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_evidence_v1\reference_fresh'
```

Anaconda Prompt / CMD (explicit existing interpreter, no installation):

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_native_reference_plan_v1.py" --sim "%SIM%" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_evidence_v1\reference_cmd_fresh"
```

Validation uses the17tiny checks and commands documented in `README_S6D_NATIVE_EVIDENCE_V1.md`; four reference/census cases cover repeated IDs, exact gap offsets, out-of-piece spans and never-correct missingness. Runtime preparation additionally verifies every historical support and occurrence binding. It does not recompute historical source activity, audio identity or model accuracy.
