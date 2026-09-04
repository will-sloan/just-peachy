[CmdletBinding()]
param(
    [ValidateSet("Demo", "Live", "File", "EnrollImport", "EnrollRecord", "Profiles", "RemoveProfile", "RestoreProfile", "RebuildProfile", "Export", "Smoke", "Presets", "Devices")]
    [string]$Action = "Demo",
    [ValidateSet("fullpipe_v1_ag_dr_ir", "fullpipe_v1_ao_dr_ir")]
    [string]$PipelineId = "fullpipe_v1_ag_dr_ir",
    [ValidateSet("H2_KNOWN_ONLY", "H2_SESSION_ANONYMOUS", "H2_SESSION_MEMORY_ENHANCED")]
    [string]$ProductMode,
    [string]$H2RuntimeConfig,
    [string]$H2RuntimeConfigSha256,
    [string]$InputPath,
    [string]$ResultsRoot,
    [string]$OutputRoot,
    [string]$EnrollmentRoot,
    [string]$ExportRoot,
    [string]$SessionId,
    [Nullable[double]]$DurationSec = $null,
    [double]$Pace = 1.0,
    [string]$Device,
    [int]$SourceSampleRateHz,
    [int]$SourceChannels,
    [string]$DisplayName,
    [string]$SpeakerId,
    [string]$ProfileId,
    [string]$ArchiveId,
    [string]$Reason = "operator_removed",
    [string[]]$Wav,
    [string]$Wav1,
    [string]$Wav2,
    [string]$Wav3,
    [switch]$PlayAudio,
    [switch]$IncludeAudio,
    [switch]$RecordInputAudio,
    [switch]$NoTelemetry
)

$ErrorActionPreference = "Stop"
$evaluationRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $evaluationRoot)
$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Repository Python was not found: $python"
}

$arguments = @("-m", "app.full_pipeline_demo")
$requiredEnrollmentWavCount = 3  # Locked matrix enrollment_policy.utterance_count
$scalarWavSpecified = (
    $PSBoundParameters.ContainsKey("Wav1") -or
    $PSBoundParameters.ContainsKey("Wav2") -or
    $PSBoundParameters.ContainsKey("Wav3")
)
if ($scalarWavSpecified) {
    if ($PSBoundParameters.ContainsKey("Wav")) {
        throw "Use either -Wav or -Wav1/-Wav2/-Wav3, not both"
    }
    if (-not $Wav1 -or -not $Wav2 -or -not $Wav3) {
        throw "-Wav1, -Wav2, and -Wav3 must all be provided together"
    }
    # powershell.exe -File cannot reliably bind a command-line array. Preserve
    # -Wav for in-session callers and expose three scalar values for -File.
    $Wav = @($Wav1, $Wav2, $Wav3)
}
if ($IncludeAudio -and $Action -in @("File", "Live") -and -not $ExportRoot) {
    throw "$Action -IncludeAudio requires -ExportRoot"
}
if ($H2RuntimeConfigSha256 -and -not $H2RuntimeConfig) {
    throw "-H2RuntimeConfigSha256 requires -H2RuntimeConfig"
}
switch ($Action) {
    "Demo" { $arguments += "launch" }
    "Presets" { $arguments += "presets" }
    "Devices" { $arguments += "devices" }
    "File" {
        if (-not $InputPath) { throw "File requires -InputPath" }
        if ($null -ne $DurationSec -and $DurationSec -lt 0) {
            throw "File -DurationSec must be zero or greater"
        }
        $arguments += @("file", "--pipeline-id", $PipelineId, "--input", $InputPath, "--pace", [string]$Pace)
        if ($DurationSec -gt 0) { $arguments += @("--duration-sec", [string]$DurationSec) }
        if ($PlayAudio) { $arguments += "--play-audio" }
        if ($IncludeAudio) { $arguments += "--include-audio" }
    }
    "Live" {
        $liveDurationSec = 30.0
        if ($null -ne $DurationSec) { $liveDurationSec = [double]$DurationSec }
        if ($liveDurationSec -le 0) { throw "Live requires -DurationSec greater than zero" }
        if ($IncludeAudio -and -not $RecordInputAudio) {
            throw "Live -IncludeAudio requires -RecordInputAudio"
        }
        $arguments += @("live", "--pipeline-id", $PipelineId, "--duration-sec", [string]$liveDurationSec)
        if ($Device) { $arguments += @("--device", $Device) }
        if ($SourceSampleRateHz -gt 0) { $arguments += @("--source-sample-rate-hz", [string]$SourceSampleRateHz) }
        if ($SourceChannels -gt 0) { $arguments += @("--source-channels", [string]$SourceChannels) }
        if ($RecordInputAudio) { $arguments += "--record-input-audio" }
        if ($IncludeAudio) { $arguments += "--include-audio" }
    }
    "EnrollImport" {
        if (-not $DisplayName) { throw "EnrollImport requires -DisplayName" }
        if (-not $Wav -or $Wav.Count -ne $requiredEnrollmentWavCount) {
            throw "EnrollImport requires exactly $requiredEnrollmentWavCount -Wav PROMPT_ID=PATH values"
        }
        $arguments += @("enroll-import", "--pipeline-id", $PipelineId, "--display-name", $DisplayName)
        foreach ($value in $Wav) { $arguments += @("--wav", $value) }
        if ($SpeakerId) { $arguments += @("--speaker-id", $SpeakerId) }
    }
    "EnrollRecord" {
        if (-not $DisplayName) { throw "EnrollRecord requires -DisplayName" }
        $arguments += @("enroll-record", "--pipeline-id", $PipelineId, "--display-name", $DisplayName)
        if ($SpeakerId) { $arguments += @("--speaker-id", $SpeakerId) }
        if ($Device) { $arguments += @("--device", $Device) }
        if ($SourceSampleRateHz -gt 0) { $arguments += @("--source-sample-rate-hz", [string]$SourceSampleRateHz) }
        if ($SourceChannels -gt 0) { $arguments += @("--source-channels", [string]$SourceChannels) }
    }
    "Profiles" { $arguments += "profiles" }
    "RemoveProfile" {
        if (-not $ProfileId) { throw "RemoveProfile requires -ProfileId" }
        $arguments += @("profile-remove", "--profile-id", $ProfileId, "--reason", $Reason)
    }
    "RestoreProfile" {
        if (-not $ProfileId) { throw "RestoreProfile requires -ProfileId" }
        $arguments += @("profile-restore", "--profile-id", $ProfileId)
        if ($ArchiveId) { $arguments += @("--archive-id", $ArchiveId) }
    }
    "RebuildProfile" {
        if (-not $ProfileId) { throw "RebuildProfile requires -ProfileId" }
        if (-not $Wav -or $Wav.Count -ne $requiredEnrollmentWavCount) {
            throw "RebuildProfile requires exactly $requiredEnrollmentWavCount -Wav PROMPT_ID=PATH values"
        }
        $arguments += @("profile-rebuild", "--profile-id", $ProfileId, "--pipeline-id", $PipelineId)
        foreach ($value in $Wav) { $arguments += @("--wav", $value) }
    }
    "Export" {
        if (-not $OutputRoot) { throw "Export requires -OutputRoot pointing to the completed run" }
        if (-not $ExportRoot) { throw "Export requires -ExportRoot" }
        $arguments += @("export", "--run-root", $OutputRoot, "--export-root", $ExportRoot)
        if ($IncludeAudio) {
            if (-not $InputPath) { throw "Export -IncludeAudio requires -InputPath" }
            $arguments += @("--include-audio", "--input-audio", $InputPath)
        }
    }
    "Smoke" {
        $arguments += "smoke"
        if ($InputPath) { $arguments += @("--input", $InputPath) }
        if ($NoTelemetry) { $arguments += "--no-telemetry" }
    }
}

if ($ResultsRoot -and $Action -in @("File", "Live")) { $arguments += @("--results-root", $ResultsRoot) }
if ($OutputRoot -and $Action -in @("File", "Live", "Smoke")) { $arguments += @("--output-root", $OutputRoot) }
if ($EnrollmentRoot -and $Action -in @("File", "Live", "EnrollImport", "EnrollRecord", "Profiles", "RemoveProfile", "RestoreProfile", "RebuildProfile")) {
    $arguments += @("--enrollment-root", $EnrollmentRoot)
}
if ($ExportRoot -and $Action -in @("File", "Live")) { $arguments += @("--export-root", $ExportRoot) }
if ($SessionId -and $Action -in @("File", "Live")) { $arguments += @("--session-id", $SessionId) }
if ($NoTelemetry -and $Action -in @("File", "Live")) { $arguments += "--no-telemetry" }
if ($ProductMode -and $Action -in @("File", "Live")) { $arguments += @("--product-mode", $ProductMode) }
if ($H2RuntimeConfig -and $Action -in @("Demo", "File", "Live")) {
    $arguments += @("--h2-runtime-config", $H2RuntimeConfig)
}
if ($H2RuntimeConfigSha256 -and $Action -in @("Demo", "File", "Live")) {
    $arguments += @("--h2-runtime-config-sha256", $H2RuntimeConfigSha256)
}

Push-Location $evaluationRoot
try {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Full-pipeline demo action failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
