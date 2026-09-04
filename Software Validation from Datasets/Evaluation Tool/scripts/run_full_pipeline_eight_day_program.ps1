[CmdletBinding()]
param(
    [ValidateSet('WriteTemplate','Validate','Run','Status','Monitor','Stop','ValidateCompletions')]
    [string]$Action = 'Status',
    [string]$AdapterConfig,
    [string]$TemplateOutput,
    [string]$StopReason = 'user_requested_graceful_stop',
    [switch]$Follow,
    [switch]$Json,
    [ValidateRange(2,3600)]
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$InvocationRoot = (Get-Location).Path
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Management Python is unavailable: $Python"
}

function Resolve-InvocationPath([string]$Value, [string]$DefaultValue) {
    $Selected = if ([string]::IsNullOrWhiteSpace($Value)) { $DefaultValue } else { $Value }
    if ([System.IO.Path]::IsPathRooted($Selected)) {
        return [System.IO.Path]::GetFullPath($Selected)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Selected))
}

$DefaultConfig = Join-Path $ToolRoot 'runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json'
$AdapterConfig = Resolve-InvocationPath $AdapterConfig $DefaultConfig
$TemplateOutput = Resolve-InvocationPath $TemplateOutput $DefaultConfig

$ActionMap = @{
    WriteTemplate = 'write-template'
    Validate = 'validate-config'
    Run = 'run'
    Status = 'status'
    Monitor = 'monitor'
    Stop = 'stop'
    ValidateCompletions = 'validate-completions'
}
$Arguments = @('-m', 'app.full_pipeline_eight_day_program', $ActionMap[$Action])
if ($Action -eq 'WriteTemplate') {
    $Arguments += @('--output', $TemplateOutput, '--evaluation-tool-root', $ToolRoot)
}
else {
    $Arguments += @('--adapter-config', $AdapterConfig)
}
if ($Json -and $Action -in @('Validate','Status','Monitor','ValidateCompletions')) {
    $Arguments += '--json'
}
if ($Action -eq 'Monitor') {
    $Arguments += @('--interval-seconds', [string]$IntervalSeconds)
    if ($Follow) { $Arguments += '--follow' }
}
if ($Action -eq 'Stop') {
    $Arguments += @('--reason', $StopReason)
}

Push-Location $ToolRoot
try {
    & $Python @Arguments
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "Eight-day program action $Action exited with code $ExitCode."
    }
}
finally {
    Pop-Location
}

