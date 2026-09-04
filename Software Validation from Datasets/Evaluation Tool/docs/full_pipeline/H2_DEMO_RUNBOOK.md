# H2 demonstration runbook

## Purpose

The common local application demonstrates the fixed H2 pipeline without placing model logic in the UI. It supports live microphone input, incremental file simulation through the same path, local enrollment, research diagnostics, session reset, and local export.

## Prerequisite

Use Windows PowerShell or PowerShell opened from Anaconda Prompt. Commands resolve the repository Python automatically.

```powershell
$Tool = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
Set-Location $Tool
```

List H2 presets and microphone devices:

```powershell
.\scripts\run_full_pipeline_demo.ps1 -Action Presets
.\scripts\run_full_pipeline_demo.ps1 -Action Devices
```

For a scientific demonstration, identify the controller-produced binding and
its independently published checksum before launch:

```powershell
$Repository = Split-Path -Parent (Split-Path -Parent $Tool)
$Python = Join-Path $Repository '.venv\Scripts\python.exe'
$H2Registry = Join-Path $Tool 'JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\h2_configuration_registry.yaml'
$H2Config = Join-Path $Tool 'JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\frozen_configurations\h2_demo_runtime_binding.frozen.json'
if (-not (Test-Path -LiteralPath $H2Registry -PathType Leaf) -or
    -not (Test-Path -LiteralPath $H2Config -PathType Leaf)) {
    throw 'The final v17 H2 registry and frozen binding are not both available yet. Wait for final reporting.'
}
$H2ConfigSha256 = (& $Python -c 'import pathlib, sys, yaml; print(yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["demo_runtime_binding"]["sha256"])' $H2Registry).Trim().ToLowerInvariant()
$ObservedH2ConfigSha256 = (Get-FileHash -LiteralPath $H2Config -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ObservedH2ConfigSha256 -ne $H2ConfigSha256) {
    throw "Frozen H2 binding checksum mismatch: registry=$H2ConfigSha256 observed=$ObservedH2ConfigSha256"
}
```

The expected value above comes from the separately packaged configuration
registry. Do not replace it by computing an “expected” value from the binding
itself: that would confirm only that the file is readable, not that it is the
controller-published frozen file.

The app accepts strict `h2-demo-runtime-binding.v1` multi-mode bundles and
`h2-frozen-product-configuration.v1` per-mode files. It verifies the source
file hash when supplied, canonical binding identity, exact runtime-tuning
identity, pipeline, and mode. A corrupt, stale, or missing exact entry stops
before model loading. Without a binding, the app is intentionally labelled
`ENGINEERING_BASELINE_NOT_FINAL` and is not a final scientific demo.

The preset inventory intentionally preserves the older matrix metadata value
`BLOCKED_BY_CURRENT_LARGE_STUDY_SEGMENT_CONTRACT_GUARD` for AG. That value
records the pre-H2 evidence boundary and is not the current application gate.
The H2 controller's sealed 36-case `runtime_qualification` result is the newer
authoritative evidence for native streaming. Before policy freeze the app still
labels itself `ENGINEERING_BASELINE_NOT_FINAL`; after freeze, the exact runtime
binding above is mandatory for a scientific demonstration.

## Interactive application

```powershell
.\scripts\run_full_pipeline_demo.ps1 -Action Demo `
  -H2RuntimeConfig $H2Config `
  -H2RuntimeConfigSha256 $H2ConfigSha256
```

The product pair is AG-H2 (Sherpa Giga primary) and AO-H2 (Original Sherpa fallback). Select one of the three H2 product modes before starting a session. Model switching is allowed only between sessions.

## Direct live microphone

First inspect the device index, then run a bounded session:

```powershell
.\scripts\run_full_pipeline_demo.ps1 -Action Devices
.\scripts\run_full_pipeline_demo.ps1 -Action Live `
  -PipelineId fullpipe_v1_ag_dr_ir `
  -ProductMode H2_SESSION_MEMORY_ENHANCED `
  -H2RuntimeConfig $H2Config `
  -H2RuntimeConfigSha256 $H2ConfigSha256 `
  -Device '0' `
  -DurationSec 60
```

If index 0 is not the intended device, substitute the index printed by `Devices`. The program reports the actual sample rate/channels and handles disconnect or unavailable input explicitly.

## File simulation

```powershell
$SampleAudio = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_a0281.wav'
.\scripts\run_full_pipeline_demo.ps1 -Action File `
  -PipelineId fullpipe_v1_ag_dr_ir `
  -ProductMode H2_SESSION_MEMORY_ENHANCED `
  -H2RuntimeConfig $H2Config `
  -H2RuntimeConfigSha256 $H2ConfigSha256 `
  -InputPath $SampleAudio `
  -Pace 1.0
```

Use `-Pace 1.0` for real-time playback. Engineering acceleration changes pacing only and still uses the incremental live path. Do not seek across causal state unless the application explicitly permits a safe reset.

## Matched primary-versus-fallback demonstration

After policy freeze, use the same input, product mode, real-time pacing, and
checksum-bound configuration for both candidates. Separate output roots prevent
one session from overwriting or being confused with the other:

```powershell
$ComparisonRoot = Join-Path $Tool 'JustPeachyResults\full_pipeline\matched_h2_demo'
$ComparisonAudio = $SampleAudio

.\scripts\run_full_pipeline_demo.ps1 -Action File `
  -PipelineId fullpipe_v1_ag_dr_ir `
  -ProductMode H2_SESSION_MEMORY_ENHANCED `
  -H2RuntimeConfig $H2Config `
  -H2RuntimeConfigSha256 $H2ConfigSha256 `
  -InputPath $ComparisonAudio `
  -Pace 1.0 `
  -SessionId 'matched_ag_h2' `
  -OutputRoot (Join-Path $ComparisonRoot 'AG-H2')

.\scripts\run_full_pipeline_demo.ps1 -Action File `
  -PipelineId fullpipe_v1_ao_dr_ir `
  -ProductMode H2_SESSION_MEMORY_ENHANCED `
  -H2RuntimeConfig $H2Config `
  -H2RuntimeConfigSha256 $H2ConfigSha256 `
  -InputPath $ComparisonAudio `
  -Pace 1.0 `
  -SessionId 'matched_ao_h2' `
  -OutputRoot (Join-Path $ComparisonRoot 'AO-H2')
```

AG-H2 is the primary architecture. AO-H2 is the deliberately different
Original-Sherpa fallback/reference. Treat AO-H2 as an endorsed fallback only if
the final reduced held-out regression passes; otherwise use it strictly as a
matched comparison demonstration. This comparison is useful operational
evidence, but one user-chosen audio file does not replace the controlled and
held-out campaign.

Inspect the exact selected mode, parameters, and tuning identities before the
demo:

```powershell
$Binding = Get-Content -LiteralPath $H2Config -Raw | ConvertFrom-Json
$SelectedMode = $Binding.default_product_mode
$Binding.configurations |
  Where-Object {
    $_.mode -eq $SelectedMode -and
    $_.pipeline_id -in @('fullpipe_v1_ag_dr_ir', 'fullpipe_v1_ao_dr_ir')
  } |
  ForEach-Object {
    [pscustomobject]@{
      PipelineId = $_.pipeline_id
      Mode = $_.mode
      TuningSha256 = $_.runtime_tuning_identity_sha256
      Parameters = ($_.runtime_tuning | ConvertTo-Json -Compress -Depth 5)
    }
  } | Format-List
```

The two rows must resolve to the intended pipeline IDs and the same frozen
speaker-policy tuning identity for a matched ASR comparison. The session
exports independently retain pipeline/model hashes, the complete scientific
runtime configuration, telemetry, labelled transcripts, and failures.

## Enrollment

Record prompted samples:

```powershell
.\scripts\run_full_pipeline_demo.ps1 -Action EnrollRecord -PipelineId fullpipe_v1_ag_dr_ir -DisplayName 'Alice' -Device '0'
```

Or import labelled WAV files:

```powershell
.\scripts\run_full_pipeline_demo.ps1 -Action EnrollImport -PipelineId fullpipe_v1_ag_dr_ir -DisplayName 'Alice' `
  -Wav1 'prompt_1=C:\samples\alice_1.wav' `
  -Wav2 'prompt_2=C:\samples\alice_2.wav' `
  -Wav3 'prompt_3=C:\samples\alice_3.wav'
```

The enrollment flow checks duration, level, clipping, and embedding consistency. Repeat a flagged sample instead of silently averaging it. Profiles are local, backend/checkpoint bound, and invalidated when that identity changes.

List, archive, restore, or rebuild profiles:

```powershell
.\scripts\run_full_pipeline_demo.ps1 -Action Profiles
.\scripts\run_full_pipeline_demo.ps1 -Action RemoveProfile -ProfileId '<id>'
.\scripts\run_full_pipeline_demo.ps1 -Action RestoreProfile -ProfileId '<id>'
.\scripts\run_full_pipeline_demo.ps1 -Action RebuildProfile -ProfileId '<id>' `
  -Wav1 'prompt_1=C:\samples\new_1.wav' `
  -Wav2 'prompt_2=C:\samples\new_2.wav' `
  -Wav3 'prompt_3=C:\samples\new_3.wav'
```

## Views and safe interpretation

User view shows transcript, known name or `Speaker_N`/`Unknown`, and simple tentative/confirmed state. Research view shows raw score, Top-1/Top-2 margin, evidence duration, threshold, ASR state, cluster, queue latency, RTF, CPU/RAM, and event log. Raw score is not a confidence percentage.

## Session controls and export

Reset/clear removes volatile anonymous/session memory; the UI asks whether to preserve the readable transcript. It never removes permanent enrollment profiles. Stop is graceful even if inference is active.

Export a completed session:

```powershell
.\scripts\run_full_pipeline_demo.ps1 -Action Export -OutputRoot 'C:\path\completed_run' -ExportRoot 'C:\path\export'
```

The export includes labelled transcript JSONL, readable transcript, full event log, pipeline/model/profile identities, runtime telemetry, and failures. Input audio is included only when the user enabled local recording. Nothing is uploaded.

It also includes
`manifests/scientific_runtime_configuration.json`, which records configuration
status, source path and SHA-256, canonical binding identity, selected mode, and
exact runtime-tuning identity. These values are also present in live session
status and pipeline identity. The source session retains
`manifests/demo_runtime_configuration.json` even if model construction fails.

## Anaconda Prompt / direct command line

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
call ".venv\Scripts\activate.bat"
cd /d "Software Validation from Datasets\Evaluation Tool"
set "H2_CONFIG=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\frozen_configurations\h2_demo_runtime_binding.frozen.json"
set "H2_REGISTRY=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\h2_complete_product_pipeline_v17\h2_configuration_registry.yaml"
for /f "delims=" %H in ('python -c "import pathlib,sys,yaml; print(yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['demo_runtime_binding']['sha256'])" "%H2_REGISTRY%"') do set "H2_CONFIG_SHA256=%H"
powershell -NoProfile -Command "$actual=(Get-FileHash -LiteralPath $env:H2_CONFIG -Algorithm SHA256).Hash.ToLowerInvariant(); if($actual -ne $env:H2_CONFIG_SHA256){throw 'Frozen H2 binding checksum mismatch'}"
python -m app.full_pipeline_demo launch --h2-runtime-config "%H2_CONFIG%" --h2-runtime-config-sha256 "%H2_CONFIG_SHA256%"
python -m app.full_pipeline_demo live --pipeline-id fullpipe_v1_ag_dr_ir --product-mode H2_SESSION_MEMORY_ENHANCED --h2-runtime-config "%H2_CONFIG%" --h2-runtime-config-sha256 "%H2_CONFIG_SHA256%" --device 0 --duration-sec 60
python -m app.full_pipeline_demo file --pipeline-id fullpipe_v1_ag_dr_ir --product-mode H2_SESSION_MEMORY_ENHANCED --h2-runtime-config "%H2_CONFIG%" --h2-runtime-config-sha256 "%H2_CONFIG_SHA256%" --input "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_a0281.wav" --pace 1
```

Inputs are local microphone frames or a local audio file, optional local
enrollment profiles, one H2 pipeline/mode, and the binding path/hash above.
Outputs are the immutable session directory under
`JustPeachyResults/full_pipeline/demo_sessions`, its labelled transcript and
events, runtime telemetry/failures, and an optional user-selected local export.

## Bounded final H2 demonstration

Use the matched AG-H2 and AO-H2 file-simulation commands above after the v17
policy freeze. The legacy common-demo `-Action Smoke` command intentionally
exercises the pre-pivot AG-H5/AG-H2/AO-H4 trio and is therefore not a final H2
validation command. Do not use it as evidence for this H2-only program.

The matched demonstrations exercise the two supported H2 pipeline choices
through the exact live path and preserve separate session exports. They remain
bounded operational demonstrations; the controller's development and untouched
held-out results remain the scientific evidence.
