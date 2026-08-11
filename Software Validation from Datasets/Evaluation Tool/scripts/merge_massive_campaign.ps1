[CmdletBinding()]
param(
    [string]$MachineATransfer = "",
    [string]$MachineBTransfer = "",
    [string]$CampaignId = "campaign_05_massive_release",
    [string]$EnvironmentProfile = "core-cpu",
    [string]$PythonRelativePath = ".venv\Scripts\python.exe"
)

. (Join-Path $PSScriptRoot "launch_common.ps1")
$context = Get-LaunchContext -WorkerId "machine_a" -CampaignId $CampaignId -EnvironmentProfile $EnvironmentProfile -PythonRelativePath $PythonRelativePath
Show-LaunchIdentity -Context $context
if (-not $MachineATransfer) {
    $MachineATransfer = Join-Path $context.RepositoryRoot "transfer_packages\$CampaignId\machine_a"
}
if (-not $MachineBTransfer) {
    $MachineBTransfer = Join-Path $context.RepositoryRoot "transfer_packages\$CampaignId\machine_b"
}
$MachineATransfer = [System.IO.Path]::GetFullPath($MachineATransfer)
$MachineBTransfer = [System.IO.Path]::GetFullPath($MachineBTransfer)
$runEvaluation = Join-Path $context.EvaluationRoot "run_evaluation.py"
foreach ($transfer in @($MachineATransfer, $MachineBTransfer)) {
    Invoke-Checked -FilePath $context.Python -Arguments @(
        $runEvaluation, "campaign", "validate-transfer",
        "--campaign-root", $context.CampaignRoot,
        "--transfer-root", $transfer
    )
}
Invoke-Checked -FilePath $context.Python -Arguments @(
    $runEvaluation, "campaign", "merge-results",
    "--campaign-root", $context.CampaignRoot,
    "--transfer-root", $MachineATransfer,
    "--transfer-root", $MachineBTransfer
)
Invoke-Checked -FilePath $context.Python -Arguments @(
    $runEvaluation, "campaign", "validate-merged",
    "--campaign-root", $context.CampaignRoot
)
Write-Host "Merged and validated campaign: $($context.CampaignRoot)"
