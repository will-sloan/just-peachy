# Freeze spatial cue controls

`s6c_cue_variants.py` creates the registered three seeded uninformative controls
and the explicitly oracle-like nominal-geometry diagnostic. It reads only the
existing sanitized delivered telemetry, canonical scene geometry and bound
reference support. It runs no models and never changes source/capture audio.

Null controls permute valid angle contents across the whole bank with fixed
seeds 11/29/47, preserving the bank angle distribution and every destination
packet's validity, energy, reliability, sequence and delivery/source clock.
They break source correspondence rather than applying a constant rotation.
They are deliberately uninformative controls, not a physical sensor-fault model.

The nominal diagnostic replaces only valid numeric angle values on supported
sole-person estimated activity. It retains the nominal folded manual center and
records its existing ±5-degree interval separately. No front/rear resolution,
early observation or person ID enters the predictor. Outside supported regions
the original numeric cues remain unchanged to preserve delivery/missingness;
results there are not scored as ideal geometry. This is a bounded supported-
region intervention, not an all-time ideal sensor or deployment candidate.

Outputs: sanitized JSONL files under the S6C report's `cue_variants_v2` directory,
`CUE_VARIANT_INDEX_V1.json` with hashes and counts, and a separate evaluator-only
nominal supported-region mask. No evaluator fields are embedded in provider
JSONL. Existing completed outputs are verified on resume; an unreceipted file
stops rather than overwrites it.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\s6c_cue_variants.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_cue_variants.py
```

Run before outcome inspection and bind the returned index in the execution
epoch. The same command verifies a completed control set. Normal operational
profiles continue to use actual delivered telemetry or cues-off. Resource/stop
and rollback conventions are in README_S6C.md; no hardware is used.

The first preparation attempt stopped at an unidentifiable source-empty scene
whose source/output mapping is null. Its source and partial outputs are kept
under `diagnosed_attempts/cue_variants_v1` and `cue_variants`. Version2 explicitly
leaves nominal cues unchanged when mapping is unavailable and writes a new
namespace. Such rows have no nominal supported-region accuracy claim.
