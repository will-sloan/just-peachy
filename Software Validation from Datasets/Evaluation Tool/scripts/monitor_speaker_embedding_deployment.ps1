[CmdletBinding()]
param(
    [ValidateRange(5, 3600)]
    [int]$IntervalSeconds = 30,
    [switch]$Once
)

$Runner = Join-Path $PSScriptRoot 'run_speaker_embedding_deployment.ps1'
do {
    Clear-Host
    Write-Output ("Speaker embedding deployment status at {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    & $Runner -Action Status
    if (-not $Once) { Start-Sleep -Seconds $IntervalSeconds }
} while (-not $Once)
