[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Plan', 'Estimate', 'Run', 'RunOne', 'Status', 'Watch', 'Stop', 'Resume', 'Validate', 'Results')]
    [string]$Action,

    [string]$ExperimentId,

    [ValidateRange(1, 3600)]
    [int]$RefreshSeconds = 30,

    [string]$Reason = 'operator request'
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
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
