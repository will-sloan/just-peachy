[CmdletBinding()]
param(
    [string]$Workspace,
    [string]$ResultsRoot,
    [ValidateRange(5,3600)]
    [int]$IntervalSeconds = 300,
    [ValidateRange(1,10000)]
    [double]$MinimumFreeGiB = 35,
    [ValidateRange(1,10000)]
    [double]$TargetFreeGiB = 80,
    [switch]$Once,
    [switch]$DryRun,
    [switch]$DisableActiveLongSessionCompression
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Guardian = Join-Path $PSScriptRoot 'maintain_h2_storage.py'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project Python is unavailable: $Python"
}
if (-not (Test-Path -LiteralPath $Guardian -PathType Leaf)) {
    throw "Storage guardian is unavailable: $Guardian"
}
if ([string]::IsNullOrWhiteSpace($Workspace)) {
    $Workspace = Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
}
if ([string]::IsNullOrWhiteSpace($ResultsRoot)) {
    $ResultsRoot = Join-Path $ToolRoot 'JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17'
}

$Workspace = [IO.Path]::GetFullPath($Workspace)
$ResultsRoot = [IO.Path]::GetFullPath($ResultsRoot)
$LogRoot = Join-Path $Workspace 'logs'
$StdoutPath = Join-Path $LogRoot 'storage_guardian.supervised.stdout.log'
$StderrPath = Join-Path $LogRoot 'storage_guardian.supervised.stderr.log'
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null

$Arguments = @(
    '-B',
    $Guardian,
    '--workspace', $Workspace,
    '--results-root', $ResultsRoot,
    '--interval-seconds', [string]$IntervalSeconds,
    '--minimum-free-gib', [string]$MinimumFreeGiB,
    '--target-free-gib', [string]$TargetFreeGiB
)
$Arguments += if ($Once) { '--once' } else { '--follow' }
if ($DryRun) { $Arguments += '--dry-run' }
if ($DisableActiveLongSessionCompression) {
    $Arguments += '--disable-active-long-session-compression'
}

# Append-only logs preserve prior guardian launches across controller recovery.
& $Python @Arguments 1>> $StdoutPath 2>> $StderrPath
exit $LASTEXITCODE
