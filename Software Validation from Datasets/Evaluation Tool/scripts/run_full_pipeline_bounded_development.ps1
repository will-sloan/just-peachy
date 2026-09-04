[CmdletBinding()]
param(
    [ValidateSet(
        'Plan','Prepare','Run','PrepareResources','RunResources',
        'Analyze','Freeze','Collect','Execute','Validate','Status','Stop'
    )]
    [string]$Action = 'Status',
    [string]$WorkspaceRoot,
    [string]$SourceEvidenceRoot,
    [string]$OutputRoot
)

$ErrorActionPreference = 'Stop'
$InvocationRoot = (Get-Location).Path
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Management Python is unavailable: $Python"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_pipeline_development_prompt4_reduced_8day_v1'
}
if ([string]::IsNullOrWhiteSpace($SourceEvidenceRoot)) {
    $SourceEvidenceRoot = Join-Path $ToolRoot 'automated_runs\full_pipeline_development_v1_prompt4_execution_recovery_v5_restart_contract_fix'
}
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $ToolRoot 'JustPeachyResearchSummaries\full_pipeline\development\full_pipeline_prompt4_reduced_8day_v1'
}

function Resolve-InvocationPath([string]$Value) {
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Value))
}

$WorkspaceRoot = Resolve-InvocationPath $WorkspaceRoot
$SourceEvidenceRoot = Resolve-InvocationPath $SourceEvidenceRoot
$OutputRoot = Resolve-InvocationPath $OutputRoot
$ActionMap = @{
    Plan = 'plan'
    Prepare = 'prepare'
    Run = 'run'
    PrepareResources = 'prepare-resources'
    RunResources = 'run-resources'
    Analyze = 'analyze'
    Freeze = 'freeze'
    Collect = 'collect'
    Execute = 'execute'
    Validate = 'validate'
    Status = 'status'
    Stop = 'stop'
}
$Arguments = @(
    '-m', 'app.full_pipeline_bounded_development.cli', $ActionMap[$Action],
    '--workspace-root', $WorkspaceRoot,
    '--source-evidence-root', $SourceEvidenceRoot,
    '--output-root', $OutputRoot
)

Push-Location $ToolRoot
try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Bounded Prompt-4 action failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
