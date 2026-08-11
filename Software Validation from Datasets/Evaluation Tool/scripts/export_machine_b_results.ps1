[CmdletBinding()]
param(
    [string]$Destination = "",
    [string]$CampaignId = "campaign_05_massive_release",
    [string]$EnvironmentProfile = "core-cpu",
    [string]$PythonRelativePath = ".venv\Scripts\python.exe"
)

. (Join-Path $PSScriptRoot "launch_common.ps1")
$context = Get-LaunchContext -WorkerId "machine_b" -CampaignId $CampaignId -EnvironmentProfile $EnvironmentProfile -PythonRelativePath $PythonRelativePath
Show-LaunchIdentity -Context $context
if (-not $Destination) {
    $Destination = Join-Path $context.RepositoryRoot "transfer_packages\$CampaignId\machine_b"
}
$Destination = [System.IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $Destination) {
    throw "Refusing to overwrite an existing transfer folder: $Destination"
}
New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
$runEvaluation = Join-Path $context.EvaluationRoot "run_evaluation.py"
Invoke-Checked -FilePath $context.Python -Arguments @(
    $runEvaluation, "campaign", "export-results",
    "--campaign-root", $context.CampaignRoot,
    "--assignment", $context.Assignment,
    "--destination", $Destination,
    "--environment-profile", $EnvironmentProfile
)
$manifest = Get-Content -Raw -LiteralPath (Join-Path $Destination "transfer_manifest.json") | ConvertFrom-Json
if (@($manifest.unexported_scenarios).Count -ne 0) {
    throw "Transfer is partial; unexported scenarios remain. Keep it for diagnostics but do not merge it as complete."
}
Invoke-Checked -FilePath $context.Python -Arguments @(
    $runEvaluation, "campaign", "validate-transfer",
    "--campaign-root", $context.CampaignRoot,
    "--transfer-root", $Destination
)
Write-Host "Validated Machine B transfer: $Destination"
