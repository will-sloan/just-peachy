[CmdletBinding()]
param(
    [string]$ProtocolRoot = '',
    [string]$ResultRoot = '',
    [int]$IntervalSeconds = 60,
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not $ProtocolRoot) { $ProtocolRoot = Join-Path $ToolRoot 'benchmarks\asr_commonvoice\commonvoice_60plus_asr_v1' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Management environment is missing: $Python" }

do {
    $Arguments = @('asr-commonvoice', 'status', '--protocol-root', $ProtocolRoot)
    if ($ResultRoot) { $Arguments += @('--result-root', $ResultRoot) }
    & $Python $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Read-only status failed with exit code $LASTEXITCODE" }
    if (-not $Once) { Start-Sleep -Seconds $IntervalSeconds }
} while (-not $Once)
