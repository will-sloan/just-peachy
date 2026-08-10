[CmdletBinding()]
param(
    [string]$MachineATransfer = "",
    [string]$MachineBTransfer = ""
)

. (Join-Path $PSScriptRoot "launch_common.ps1")
$context = Get-LaunchContext -WorkerId "machine_a"
Show-LaunchIdentity -Context $context
if (-not $MachineATransfer) {
    $MachineATransfer = Join-Path $context.RepositoryRoot "transfer_packages\campaign_05_massive_release\machine_a"
}
if (-not $MachineBTransfer) {
    $MachineBTransfer = Join-Path $context.RepositoryRoot "transfer_packages\campaign_05_massive_release\machine_b"
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
Write-Host "Merged and validated 41-scenario campaign: $($context.CampaignRoot)"
