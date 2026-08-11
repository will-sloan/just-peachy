[CmdletBinding()]
param(
    [string]$MachineATransfer = "",
    [string]$MachineBTransfer = ""
)

$arguments = @(
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "merge_massive_campaign.ps1"),
    "-CampaignId", "campaign_06_massive_release_cuda",
    "-EnvironmentProfile", "core-cuda",
    "-PythonRelativePath", ".stage8-envs\core-cuda\Scripts\python.exe"
)
if ($MachineATransfer) {
    $arguments += @("-MachineATransfer", $MachineATransfer)
}
if ($MachineBTransfer) {
    $arguments += @("-MachineBTransfer", $MachineBTransfer)
}
& powershell @arguments
if ($LASTEXITCODE -ne 0) {
    throw "GPU campaign merge failed with exit code $LASTEXITCODE"
}
