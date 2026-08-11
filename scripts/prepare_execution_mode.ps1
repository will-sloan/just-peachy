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
$ProductionWhisperModels = "tiny,base,small"

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
    $wingetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
    if (Test-Path -LiteralPath (Join-Path $wingetLinks "ffmpeg.exe") -PathType Leaf) {
        $env:Path = "$wingetLinks;$env:Path"
    }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        $packageRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
        $candidate = Get-ChildItem -Path (Join-Path $packageRoot "Gyan.FFmpeg_*\ffmpeg-*\bin\ffmpeg.exe") `
            -File -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($candidate) {
            $env:Path = "$($candidate.DirectoryName);$env:Path"
        }
    }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        throw "FFmpeg was installed but its executable could not be resolved."
    }
}

Push-Location $RepositoryRoot
try {
    if ($Mode -eq "cpu") {
        $installerArguments = @(
            "-ExecutionPolicy", "Bypass", "-File", (Join-Path $RepositoryRoot "install.ps1"),
            "-Profile", "dev", "-Device", "cpu", "-WhisperModels", $ProductionWhisperModels
        )
        if ($DownloadModels) { $installerArguments += "-DownloadModels" }
        if ($InstallFFmpeg) { $installerArguments += "-InstallFFmpeg" }
        if ($Recreate) { $installerArguments += "-ForceRecreateVenv" }
        Invoke-Checked -FilePath "powershell" -Arguments $installerArguments
        # The child installer can update the user PATH through WinGet, but the
        # current setup process does not inherit that change automatically.
        # Resolve the installed package here so setup and verification can run
        # back-to-back without reopening the operator terminal.
        Ensure-FFmpeg
        $python = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
        Invoke-Checked -FilePath $python -Arguments @(
            "scripts\verify_install.py", "--profile", "dev", "--device", "cpu",
            "--cache-root", $ModelRoot, "--whisper", $ProductionWhisperModels, "--require-models"
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
        "--cache-root", $ModelRoot, "--whisper", $ProductionWhisperModels, "--require-models"
    )
    Write-Host "[PASS] core-cuda is ready: $python"
} finally {
    Pop-Location
}
