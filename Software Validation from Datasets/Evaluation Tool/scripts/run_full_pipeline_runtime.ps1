[CmdletBinding()]
param(
    [ValidateSet("FileSmoke", "MicrophoneSmoke", "EnrollmentSmoke", "ComponentSmoke", "Status", "MatrixStatus")]
    [string]$Action = "Status",
    [string]$PipelineId = "fullpipe_v1_ao_dr_ir",
    [string]$InputPath,
    [string]$OutputRoot,
    [string]$EnrollmentRoot,
    [double]$DurationSec = 10.0,
    [string]$Device,
    [switch]$Realtime,
    [switch]$NoTelemetry,
    [string[]]$Backend
)

$ErrorActionPreference = "Stop"
$evaluationRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $evaluationRoot)
$python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Repository Python was not found: $python"
}
if (-not $InputPath) {
    $InputPath = Join-Path $evaluationRoot "artifacts\realtime_test_audio\aew_rxr_eey_arctic_a0301_concat.wav"
}

$arguments = @("-m", "app.full_pipeline")
switch ($Action) {
    "FileSmoke" {
        $arguments += @("file-smoke", "--pipeline-id", $PipelineId, "--input", $InputPath)
        if ($DurationSec -gt 0) { $arguments += @("--duration-sec", [string]$DurationSec) }
        if ($Realtime) { $arguments += "--realtime" }
    }
    "MicrophoneSmoke" {
        if ($DurationSec -le 0) { throw "MicrophoneSmoke requires DurationSec greater than zero" }
        $arguments += @("microphone-smoke", "--pipeline-id", $PipelineId, "--duration-sec", [string]$DurationSec)
        if ($Device) { $arguments += @("--device", $Device) }
    }
    "EnrollmentSmoke" {
        $arguments += @("enrollment-smoke", "--input", $InputPath)
        foreach ($name in $Backend) { $arguments += @("--backend", $name) }
    }
    "ComponentSmoke" {
        $arguments += @("component-smoke", "--input", $InputPath)
        if ($DurationSec -gt 0) { $arguments += @("--duration-sec", [string]$DurationSec) }
    }
    "Status" { $arguments += "status" }
    "MatrixStatus" { $arguments += "matrix-status" }
}
if ($OutputRoot -and $Action -in @("FileSmoke", "MicrophoneSmoke", "EnrollmentSmoke", "ComponentSmoke", "Status")) {
    $arguments += @("--output-root", $OutputRoot)
}
if ($EnrollmentRoot -and $Action -in @("FileSmoke", "MicrophoneSmoke")) {
    $arguments += @("--enrollment-root", $EnrollmentRoot)
}
if ($NoTelemetry -and $Action -in @("FileSmoke", "MicrophoneSmoke", "ComponentSmoke")) {
    $arguments += "--no-telemetry"
}

Push-Location $evaluationRoot
try {
    & $python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Full-pipeline runtime action failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
