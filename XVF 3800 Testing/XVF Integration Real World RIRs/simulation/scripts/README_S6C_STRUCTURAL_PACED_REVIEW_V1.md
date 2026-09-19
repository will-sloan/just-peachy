# Structural paced preparation review V1

Purpose: independently verify the finite preparation for C067, C122, C121, C079, C117 and C118: exact epoch4/V7 profiles, 16 original cases plus four repeats, both same-tap routes, 240 ordered cells, no-gallery/cue policy and canonical source metadata.

Inputs are SHA-pinned scope, manifest, epoch, registry and panel JSON; their bound original INPUT_INDEX, 12 profile JSONs, 16 per-case source JSONs, unchanged adapter source/README bytes and earlier reviewed preparation metadata. The script parses and executes only the held two pure source-record constructors. It does not import the application, native worker, models or scorers; it does not read audio, cue logs or model files, or rerun native fixtures.

Output is one fresh JSON review receipt with exact source-buffer hashes, check count, grid/source arithmetic and explicit limits. Existing output is never overwritten. The empty preparation namespace check intentionally fails after execution has started; the original receipt remains the record of the review at preparation time. Metadata comparison does not replace later resource/quiet admission or original PCM/model integrity checks.

Prerequisite: the existing ANALYSIS Python environment. No package installation or model setup is needed. Do not run during a reserved quiet paced period.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$analysis = Join-Path $sim 'staging\s5_text_metrics\analysis_env\Scripts\python.exe'
& $analysis -B (Join-Path $sim 'scripts\s6c_structural_paced_review_v1.py') --output (Join-Path $sim 'reports\S6C\20260910T123540Z\independent_review\STRUCTURAL_PACED_PREPARATION_REVIEW_V1.json')
```

Anaconda Prompt / Windows CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" -B "%SIM%\scripts\s6c_structural_paced_review_v1.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\STRUCTURAL_PACED_PREPARATION_REVIEW_V1.json"
```

For a later metadata-only reproduction before execution, choose a fresh receipt filename; do not replace V1. Any change to the pinned authoritative inputs requires a separately reviewed version. The recorded source-duration sum is 10726.905 seconds across repeated cells, not predicted wall time or distinct source duration.

