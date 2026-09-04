[CmdletBinding()]
param(
    [ValidateSet('Audit','Prepare','Validate','Plan','Smoke','Run','Status','Stop','Analyze','Collect')]
    [string]$Action = 'Status',
    [ValidateRange(1,3)]
    [int]$ParallelPipelines = 2,
    [switch]$Background,
    [switch]$OpenMonitor,
    [ValidateRange(2,3600)]
    [int]$MonitorIntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
$Monitor = Join-Path $ToolRoot 'scripts\monitor_diarization_product_v2.ps1'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Management Python is unavailable: $Python"
}

if ($Action -eq 'Run' -and $Background) {
    $LogRoot = Join-Path $ToolRoot 'JustPeachyResults\diarization_product_v2_development'
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
    $StdoutLog = Join-Path $LogRoot 'background_controller.stdout.log'
    $StderrLog = Join-Path $LogRoot 'background_controller.stderr.log'
    $arguments = @(
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $PSCommandPath),
        '-Action', 'Run',
        '-ParallelPipelines', [string]$ParallelPipelines
    )
    if ($OpenMonitor) {
        $arguments += @('-OpenMonitor', '-MonitorIntervalSeconds', [string]$MonitorIntervalSeconds)
    }
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $ToolRoot -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
    [ordered]@{
        status = 'BACKGROUND_CONTROLLER_STARTED'
        pid = $process.Id
        stdout_log = $StdoutLog
        stderr_log = $StderrLog
    } | ConvertTo-Json
    exit 0
}

if ($Action -eq 'Run' -and $OpenMonitor) {
    $arguments = @(
        '-NoExit',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $Monitor),
        '-Follow',
        '-IntervalSeconds', [string]$MonitorIntervalSeconds
    )
    Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $ToolRoot -WindowStyle Normal | Out-Null
}

$command = $Action.ToLowerInvariant()
$arguments = @($Launcher, 'diarization-product-v2', $command)
if ($Action -eq 'Run') {
    $arguments += @('--parallel-pipelines', [string]$ParallelPipelines)
}

Push-Location $ToolRoot
try {
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Diarization Product V2 action failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
