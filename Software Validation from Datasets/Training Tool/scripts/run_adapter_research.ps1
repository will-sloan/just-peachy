[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Plan', 'Estimate', 'Qualify', 'Run', 'RunOne', 'Status', 'Watch', 'Stop', 'Resume', 'Validate', 'Results')]
    [string]$Action,

    [string]$ExperimentId,

    [ValidateRange(1, 3600)]
    [int]$RefreshSeconds = 30,

    [string]$Reason = 'operator request',

    [string]$WslDistro,
    [string]$RepoRoot,
    [string]$DataRoot,
    [string]$TrainingRoot,
    [string]$ModelRoot,
    [string]$RunRoot
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($RepoRoot) { $env:JP_REPO_ROOT = $RepoRoot }
if ($DataRoot) { $env:JP_DATA_ROOT = $DataRoot }
if ($TrainingRoot) { $env:JP_TRAINING_ROOT = $TrainingRoot }
if ($ModelRoot) { $env:JP_MODEL_ROOT = $ModelRoot }
if ($RunRoot) { $env:JP_RUN_ROOT = $RunRoot }
if ($WslDistro) { $env:JP_WSL_DISTRO = $WslDistro }

$RepositoryRoot = if ($env:JP_REPO_ROOT) {
    (Resolve-Path -LiteralPath $env:JP_REPO_ROOT).Path
} else {
    (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
}
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository Python environment is unavailable: $Python"
}

Push-Location $ToolRoot
try {
    switch ($Action) {
        'Plan' {
            & $Python -m training_data.adapter_research plan
        }
        'Estimate' {
            & $Python -m training_data.adapter_research estimate
        }
        'Qualify' {
            & $Python -m training_data.adapter_research qualify
        }
        'Run' {
            & $Python -m training_data.adapter_research run
        }
        'RunOne' {
            if ([string]::IsNullOrWhiteSpace($ExperimentId)) {
                throw '-ExperimentId is required for -Action RunOne.'
            }
            & $Python -m training_data.adapter_research run-one --experiment-id $ExperimentId
        }
        'Status' {
            & $Python -m training_data.adapter_research status
        }
        'Watch' {
            while ($true) {
                Clear-Host
                & $Python -m training_data.adapter_research status-compact
                if ($LASTEXITCODE -ne 0) {
                    exit $LASTEXITCODE
                }
                Start-Sleep -Seconds $RefreshSeconds
            }
        }
        'Stop' {
            & $Python -m training_data.adapter_research stop --reason $Reason
        }
        'Resume' {
            & $Python -m training_data.adapter_research resume
        }
        'Validate' {
            & $Python -m training_data.adapter_research validate
        }
        'Results' {
            & $Python -m training_data.adapter_research results
        }
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
