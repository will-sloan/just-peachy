[CmdletBinding()]
param(
    [string]$Workspace,
    [string]$ResultsRoot,
    [string]$SummaryRoot,
    [string]$Config,
    [ValidateRange(1,3600)]
    [int]$IntervalSeconds = 5,
    [switch]$Follow,
    [switch]$Once,
    [switch]$Json,
    [switch]$IncludeLiveCaseStatus,
    [switch]$NoMilestoneSound
)

$ErrorActionPreference = 'Stop'
$ReadOnlyMonitor = Join-Path $PSScriptRoot 'monitor_h2_product_program_readonly.ps1'
if (-not (Test-Path -LiteralPath $ReadOnlyMonitor -PathType Leaf)) {
    throw "Read-only H2 monitor is unavailable: $ReadOnlyMonitor"
}
& $ReadOnlyMonitor @PSBoundParameters
exit $LASTEXITCODE
