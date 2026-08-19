[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Apply', 'Verify')]
    [string]$Action = 'Plan'
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = if ($env:JP_REPO_ROOT) {
    (Resolve-Path -LiteralPath $env:JP_REPO_ROOT).Path
} else {
    (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
}
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
$ToolRoot = Join-Path $RepositoryRoot 'Software Validation from Datasets\Training Tool'
$TrainingRoot = if ($env:JP_TRAINING_ROOT) { $env:JP_TRAINING_ROOT } else { Join-Path $RepositoryRoot 'training' }
$DataRoot = if ($env:JP_DATA_ROOT) { $env:JP_DATA_ROOT } else { Join-Path $RepositoryRoot 'Software Validation from Datasets' }
$Legacy = Join-Path $TrainingRoot 'datasets\common_voice\english\cv-corpus-26.0-2026-06-12\prepared\en'
$Preferred = Join-Path $DataRoot 'Raw Datasets (Not formatted)\Common Voice\cv-corpus-26.0-2026-06-12\prepared\en'

Push-Location $ToolRoot
try {
    if ($Action -eq 'Plan') {
        [ordered]@{ ACTION = 'Plan'; SOURCE = $Legacy; TARGET = $Preferred; RAW_AUDIO_GIT_TRACKED = $false } | ConvertTo-Json
        exit 0
    }
    if ($Action -eq 'Apply') {
        & $Python -m training_data.asset_layout reconcile
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ((Test-Path -LiteralPath $Legacy) -and -not ((Get-Item -LiteralPath $Legacy -Force).LinkType)) {
            $Remaining = (Get-ChildItem -LiteralPath $Legacy -File -Recurse | Measure-Object).Count
            if ($Remaining -ne 0) { throw "Legacy source still has $Remaining files." }
            [System.IO.Directory]::Delete($Legacy, $true)
        }
        if (-not (Test-Path -LiteralPath $Legacy)) {
            New-Item -ItemType Directory -Path (Split-Path $Legacy -Parent) -Force | Out-Null
            New-Item -ItemType Junction -Path $Legacy -Target $Preferred | Out-Null
        }
    }
    & $Python -m training_data.asset_layout verify
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
