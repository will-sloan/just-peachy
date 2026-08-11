[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("cpu", "cuda")]
    [string]$Mode,

    [switch]$DownloadModels,
    [switch]$InstallFFmpeg,
    [switch]$Recreate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ModelRoot = Join-Path $RepositoryRoot "models\cache"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Ensure-FFmpeg {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Host "[PASS] FFmpeg is available."
        return
    }
    if (-not $InstallFFmpeg) {
        throw "FFmpeg is missing. Rerun with -InstallFFmpeg or install it and reopen PowerShell."
    }
    $winget = Get-Command winget -ErrorAction Stop
    Invoke-Checked -FilePath $winget.Source -Arguments @(
        "install", "--id", "Gyan.FFmpeg", "-e",
        "--accept-package-agreements", "--accept-source-agreements"
    )
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath;$env:Path"
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        throw "FFmpeg was installed but is not visible. Reopen PowerShell and rerun this command."
    }
}

Push-Location $RepositoryRoot
try {
    if ($Mode -eq "cpu") {
        $installerArguments = @(
            "-ExecutionPolicy", "Bypass", "-File", (Join-Path $RepositoryRoot "install.ps1"),
            "-Profile", "dev", "-Device", "cpu", "-WhisperModels", "base"
        )
        if ($DownloadModels) { $installerArguments += "-DownloadModels" }
        if ($InstallFFmpeg) { $installerArguments += "-InstallFFmpeg" }
        if ($Recreate) { $installerArguments += "-ForceRecreateVenv" }
        Invoke-Checked -FilePath "powershell" -Arguments $installerArguments
        $python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
        Invoke-Checked -FilePath $python -Arguments @(
            "scripts\verify_install.py", "--profile", "dev", "--device", "cpu",
            "--cache-root", $ModelRoot, "--whisper", "base", "--require-models"
        )
        Write-Host "[PASS] core-cpu is ready: $python"
        return
    }

    Ensure-FFmpeg
    $stage8Arguments = @(
        "-ExecutionPolicy", "Bypass", "-File",
        (Join-Path $RepositoryRoot "scripts\install_stage8_profile.ps1"),
        "-Profile", "core-cuda"
    )
    if ($DownloadModels) { $stage8Arguments += "-DownloadModels" }
    if ($Recreate) { $stage8Arguments += "-Recreate" }
    Invoke-Checked -FilePath "powershell" -Arguments $stage8Arguments
    $python = Join-Path $RepositoryRoot ".stage8-envs\core-cuda\Scripts\python.exe"
    Invoke-Checked -FilePath $python -Arguments @(
        "scripts\verify_install.py", "--profile", "dev", "--device", "cuda",
        "--cache-root", $ModelRoot, "--whisper", "base", "--require-models"
    )
    Write-Host "[PASS] core-cuda is ready: $python"
} finally {
    Pop-Location
}
