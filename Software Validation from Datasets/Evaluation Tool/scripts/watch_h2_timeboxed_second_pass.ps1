[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][int]$FirstManagerPid,
    [Parameter(Mandatory=$true)][string]$ToolRoot,
    [Parameter(Mandatory=$true)][string]$Workspace,
    [Parameter(Mandatory=$true)][string]$ResultsRoot,
    [Parameter(Mandatory=$true)][string]$SummaryRoot,
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][datetime]$DeadlineUtc,
    [int]$PackagingReserveMinutes = 75
)

$ErrorActionPreference = 'Stop'
$ToolRoot = [IO.Path]::GetFullPath($ToolRoot)
$Workspace = [IO.Path]::GetFullPath($Workspace)
$ResultsRoot = [IO.Path]::GetFullPath($ResultsRoot)
$SummaryRoot = [IO.Path]::GetFullPath($SummaryRoot)
$Config = [IO.Path]::GetFullPath($Config)
$Python = [IO.Path]::GetFullPath((Join-Path $ToolRoot '..\..\.venv\Scripts\python.exe'))
$Controller = [IO.Path]::GetFullPath((Join-Path $ToolRoot 'scripts\h2_timeboxed_completion.py'))
$Log = Join-Path $Workspace 'logs\timeboxed_second_pass_watcher.log'

"$(Get-Date -Format o) waiting for first manager PID $FirstManagerPid" | Add-Content -LiteralPath $Log
Wait-Process -Id $FirstManagerPid -ErrorAction SilentlyContinue

if ((Get-Date).ToUniversalTime() -ge $DeadlineUtc.ToUniversalTime()) {
    "$(Get-Date -Format o) deadline reached; second pass not launched" | Add-Content -LiteralPath $Log
    exit 0
}

"$(Get-Date -Format o) launching remaining-time engineering/report pass" | Add-Content -LiteralPath $Log
& $Python -B $Controller `
    --tool-root $ToolRoot `
    --workspace $Workspace `
    --results-root $ResultsRoot `
    --summary-root $SummaryRoot `
    --config $Config `
    --deadline-utc ($DeadlineUtc.ToUniversalTime().ToString('o').Replace('+00:00','Z')) `
    --packaging-reserve-minutes $PackagingReserveMinutes `
    *>> $Log
exit $LASTEXITCODE
