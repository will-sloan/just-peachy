[CmdletBinding()]
param([string]$Destination = "")

$arguments = @(
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $PSScriptRoot "export_machine_a_results.ps1"),
    "-CampaignId", "campaign_06_massive_release_cuda",
    "-EnvironmentProfile", "core-cuda",
    "-PythonRelativePath", ".stage8-envs\core-cuda\Scripts\python.exe"
)
if ($Destination) {
    $arguments += @("-Destination", $Destination)
}
& powershell @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Machine A GPU export failed with exit code $LASTEXITCODE"
}
