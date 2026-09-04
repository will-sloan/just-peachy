[CmdletBinding()]
param(
    [ValidateSet('Validate','Plan','Run','RunControlled','RunCHIME6','RunVOICES','Status','Stop','Analyze','Collect','ValidateFinal')]
    [string]$Action = 'Status',
    [ValidateRange(1,2)]
    [int]$ParallelBackends = 2,
    [ValidateRange(500,1000)]
    [int]$BootstrapRepetitions = 500,
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
$Monitor = Join-Path $ToolRoot 'scripts\monitor_hybrid_speaker_attribution_final_evaluation.ps1'
$ResultRoot = Join-Path $ToolRoot 'JustPeachyResults\hybrid_speaker_attribution_product_v2_final_evaluation'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Management Python is unavailable: $Python"
}

if ($Action -eq 'Run' -and $Background) {
    New-Item -ItemType Directory -Path $ResultRoot -Force | Out-Null
    $StdoutLog = Join-Path $ResultRoot 'background_controller.stdout.log'
    $StderrLog = Join-Path $ResultRoot 'background_controller.stderr.log'
    $arguments = @(
        '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath),
        '-Action', 'Run', '-ParallelBackends', [string]$ParallelBackends,
        '-BootstrapRepetitions', [string]$BootstrapRepetitions
    )
    if ($OpenMonitor) {
        $arguments += @('-OpenMonitor', '-MonitorIntervalSeconds', [string]$MonitorIntervalSeconds)
    }
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $ToolRoot -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru
    [ordered]@{ status = 'BACKGROUND_CONTROLLER_STARTED'; pid = $process.Id; stdout_log = $StdoutLog; stderr_log = $StderrLog } | ConvertTo-Json
    exit 0
}

if ($Action -eq 'Run' -and $OpenMonitor) {
    $arguments = @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $Monitor), '-Follow', '-IntervalSeconds', [string]$MonitorIntervalSeconds)
    Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $ToolRoot -WindowStyle Normal | Out-Null
}

$command = switch ($Action) {
    'Run' { 'full' }
    'RunControlled' { 'run-controlled' }
    'RunCHIME6' { 'run-chime6' }
    'RunVOICES' { 'run-voices' }
    'ValidateFinal' { 'validate-final' }
    default { $Action.ToLowerInvariant() }
}
$arguments = @($Launcher, 'hybrid-final-evaluation', $command)
if ($Action -in @('Run','RunControlled')) {
    $arguments += @('--parallel-backends', [string]$ParallelBackends)
}
if ($Action -in @('Run','Analyze')) {
    $arguments += @('--bootstrap-repetitions', [string]$BootstrapRepetitions)
}

Push-Location $ToolRoot
try {
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Final hybrid evaluation action failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

