[CmdletBinding()]
param([switch]$Recreate)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$Installer = Join-Path $RepositoryRoot "scripts\install_stage8_profile.ps1"

Push-Location $RepositoryRoot
try {
    foreach ($Profile in @("edge-cpu", "moonshine-edge", "onnx")) {
        $Arguments = @("-ExecutionPolicy", "Bypass", "-File", $Installer, "-Profile", $Profile, "-DownloadModels")
        if ($Recreate) { $Arguments += "-Recreate" }
        & powershell @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Failed to prepare isolated profile: $Profile" }
    }
    Write-Host "[PASS] Edge profiles and explicitly approved local assets are prepared."
    Write-Host "No campaign was planned or started."
} finally {
    Pop-Location
}
