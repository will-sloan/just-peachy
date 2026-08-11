[CmdletBinding()]
param([string]$PrerequisiteEvidence = "")

$arguments = @(
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "analyze_massive_campaign.ps1"),
    "-CampaignId", "campaign_06_massive_release_cuda",
    "-EnvironmentProfile", "core-cuda",
    "-PythonRelativePath", ".stage8-envs\core-cuda\Scripts\python.exe"
)
if ($PrerequisiteEvidence) {
    $arguments += @("-PrerequisiteEvidence", $PrerequisiteEvidence)
}
& powershell @arguments
if ($LASTEXITCODE -ne 0) {
    throw "GPU campaign analysis failed with exit code $LASTEXITCODE"
}
