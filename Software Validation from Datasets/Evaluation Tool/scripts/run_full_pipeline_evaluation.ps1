[CmdletBinding()]
param(
    [ValidateSet('Audit','Prepare','Validate','Plan','Smoke','RunDevelopment','Freeze','RunEvaluation','Status','Stop','Analyze','Collect')]
    [string]$Action = 'Status',
    [string]$WorkspaceRoot,
    [string[]]$PipelineId = @(),
    [string[]]$ProtocolId = @(),
    [ValidateSet('accuracy','resources')]
    [string]$MeasurementMode = 'accuracy',
    [ValidateRange(1,2)]
    [int]$ParallelJobs = 2,
    [ValidateSet('all','development','evaluation')]
    [string]$Split = 'all',
    [ValidateRange(0,[int]::MaxValue)]
    [int]$Seed = 5107,
    [switch]$VerifyAudio,
    [string]$OutputRoot,
    [switch]$OpenMonitor,
    [ValidateRange(2,3600)]
    [int]$MonitorIntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$InvocationRoot = (Get-Location).Path
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Monitor = Join-Path $PSScriptRoot 'monitor_full_pipeline_evaluation.ps1'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Management Python is unavailable: $Python"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_speech_pipeline_v1'
} elseif (-not [System.IO.Path]::IsPathRooted($WorkspaceRoot)) {
    $WorkspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $WorkspaceRoot))
}
if (-not [string]::IsNullOrWhiteSpace($OutputRoot) -and
    -not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $OutputRoot))
}
if ($MeasurementMode -eq 'resources' -and $ParallelJobs -ne 1 -and $Action -in @('RunDevelopment','RunEvaluation')) {
    throw 'Matched resource measurements must use -ParallelJobs 1.'
}

$ActionMap = @{
    Audit='audit'; Prepare='prepare'; Validate='validate'; Plan='plan'; Smoke='smoke'
    RunDevelopment='run-development'; Freeze='freeze'; RunEvaluation='run-evaluation'
    Status='status'; Stop='stop'; Analyze='analyze'; Collect='collect'
}
$arguments = @(
    '-m', 'app.full_pipeline_evaluation', $ActionMap[$Action],
    '--workspace-root', $WorkspaceRoot
)
foreach ($value in $PipelineId) {
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        $arguments += @('--pipeline-id', $value)
    }
}
foreach ($value in $ProtocolId) {
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        $arguments += @('--protocol-id', $value)
    }
}
if ($Action -in @('RunDevelopment','RunEvaluation') -or
    ($Action -eq 'Plan' -and $PSBoundParameters.ContainsKey('MeasurementMode'))) {
    $arguments += @('--measurement-mode', $MeasurementMode)
}
if ($Action -in @('RunDevelopment','RunEvaluation')) {
    $arguments += @('--parallel-jobs', [string]$ParallelJobs)
}
if ($Action -eq 'Plan' -and $Split -ne 'all') {
    $arguments += @('--split', $Split)
}
if ($Action -eq 'Prepare') {
    $arguments += @('--seed', [string]$Seed)
}
if ($Action -eq 'Validate' -and $VerifyAudio) {
    $arguments += '--verify-audio'
}
if ($Action -eq 'Smoke' -and -not [string]::IsNullOrWhiteSpace($OutputRoot)) {
    $arguments += @('--output-root', $OutputRoot)
}

if ($OpenMonitor -and $Action -in @('RunDevelopment','RunEvaluation')) {
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $Monitor),
        '-WorkspaceRoot', ('"{0}"' -f $WorkspaceRoot),
        '-Follow', '-IntervalSeconds', [string]$MonitorIntervalSeconds
    ) -WorkingDirectory $ToolRoot -WindowStyle Normal | Out-Null
}

Push-Location $ToolRoot
try {
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Full-pipeline evaluation action failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
