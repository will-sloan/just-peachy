[CmdletBinding()]
param(
    [ValidateSet('Audit','Plan','Validate','Smoke','Run','Status','Stop','Analyze','Collect')]
    [string]$Action = 'Status',
    [ValidateSet('chime6','voices')]
    [string[]]$Dataset = @('chime6','voices'),
    [string[]]$Backend = @('sherpa_onnx_diarization'),
    [int]$MaxUnits = 0
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$arguments = @((Join-Path $ToolRoot 'run_evaluation.py'), 'diarization-native-campaign', $Action.ToLowerInvariant())
if ($Action -eq 'Run') {
    foreach ($value in $Dataset) { $arguments += @('--dataset', $value) }
    foreach ($value in $Backend) { $arguments += @('--backend', $value) }
    if ($MaxUnits -gt 0) { $arguments += @('--max-units', [string]$MaxUnits) }
}
Push-Location $ToolRoot
try {
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Native campaign action failed: $LASTEXITCODE" }
}
finally { Pop-Location }

