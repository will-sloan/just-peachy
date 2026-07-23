[CmdletBinding()]
param(
    [ValidateSet("core", "inference", "full", "dev")]
    [string]$Profile = "inference",

    [ValidateSet("auto", "cpu", "cuda")]
    [string]$Device = "auto",

    [string]$Python = "",
    [string]$WhisperModels = "base",
    [switch]$DownloadModels,
    [switch]$InstallFFmpeg,
    [switch]$ForceRecreateVenv
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $MyInvocation.MyCommand.Path))
$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$LogDirectory = Join-Path $ProjectRoot ".install-logs"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDirectory "install_$Timestamp.log"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Test-PythonExecutable {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    & $Path -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Resolve-BasePython {
    if ($Python) {
        $command = Get-Command $Python -ErrorAction Stop
        & $command.Source -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "The selected interpreter must be Python 3.10-3.12: $($command.Source)"
        }
        return [pscustomobject]@{ FilePath = $command.Source; Prefix = @() }
    }

    $launcher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3.12 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ FilePath = $launcher.Source; Prefix = @("-3.12") }
        }
    }

    $pythonCommand = Get-Command "python" -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        & $pythonCommand.Source -c "import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ FilePath = $pythonCommand.Source; Prefix = @() }
        }
    }

    throw "Python 3.10-3.12 was not found. Install Python 3.12, then rerun this script."
}

function Backup-ExistingVenv {
    param([switch]$Broken)

    if (-not (Test-Path -LiteralPath $VenvPath)) {
        return
    }
    $resolvedVenv = [System.IO.Path]::GetFullPath($VenvPath)
    $expectedPrefix = $ProjectRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedVenv.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to move a virtual environment outside the project: $resolvedVenv"
    }
    $backupKind = if ($Broken) { "broken" } else { "backup" }
    $backupPath = Join-Path $ProjectRoot ".venv.$backupKind.$Timestamp"
    Write-Host "Backing up existing virtual environment to $backupPath"
    Move-Item -LiteralPath $resolvedVenv -Destination $backupPath
}

function Ensure-FFmpeg {
    if (Get-Command "ffmpeg" -ErrorAction SilentlyContinue) {
        Write-Host "[PASS] FFmpeg is available."
        return
    }

    if (-not $InstallFFmpeg) {
        Write-Warning "FFmpeg is missing. Rerun with -InstallFFmpeg or install it and reopen the terminal."
        return
    }

    $winget = Get-Command "winget" -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "WinGet is unavailable. Install FFmpeg manually and ensure ffmpeg.exe is on PATH."
    }
    Invoke-Native $winget.Source @(
        "install", "--id", "Gyan.FFmpeg", "-e",
        "--accept-package-agreements", "--accept-source-agreements"
    )

    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath;$env:Path"
    $wingetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
    $ffmpegLink = Join-Path $wingetLinks "ffmpeg.exe"
    if (Test-Path -LiteralPath $ffmpegLink -PathType Leaf) {
        $env:Path = "$wingetLinks;$env:Path"
    }
    if (-not (Get-Command "ffmpeg" -ErrorAction SilentlyContinue)) {
        Write-Warning "FFmpeg was installed but is not visible yet. Reopen the terminal after setup."
    }
}

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
Start-Transcript -Path $LogPath -Force | Out-Null
Push-Location $ProjectRoot

try {
    Write-Host "Installing just-peachy profile '$Profile' in $ProjectRoot"
    $venvIsUsable = Test-PythonExecutable $VenvPython
    if ($ForceRecreateVenv -or -not $venvIsUsable) {
        $basePython = Resolve-BasePython
        if (Test-Path -LiteralPath $VenvPath) {
            Backup-ExistingVenv -Broken:(-not $venvIsUsable)
        }
        Write-Host "Creating .venv with Python 3.10-3.12..."
        Invoke-Native $basePython.FilePath @($basePython.Prefix + @("-m", "venv", $VenvPath))
    } else {
        Write-Host "[PASS] Existing .venv is usable."
    }

    if (-not (Test-PythonExecutable $VenvPython)) {
        throw "The virtual environment was created but its Python executable is not usable."
    }

    Invoke-Native $VenvPython @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
    $requirementsPath = Join-Path $ProjectRoot "requirements\$Profile.txt"
    if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
        throw "Dependency profile does not exist: $requirementsPath"
    }
    Invoke-Native $VenvPython @("-m", "pip", "install", "-r", $requirementsPath)

    if ($Profile -ne "core") {
        Ensure-FFmpeg
    }

    if ($DownloadModels) {
        if ($Profile -eq "core") {
            throw "-DownloadModels requires the inference, full, or dev profile."
        }
        $bootstrapPath = Join-Path $ProjectRoot "scripts\bootstrap_models.py"
        Invoke-Native $VenvPython @(
            $bootstrapPath,
            "--whisper", $WhisperModels,
            "--speechbrain-ecapa",
            "--silero"
        )
    }

    $verifyPath = Join-Path $ProjectRoot "scripts\verify_install.py"
    $verifyArguments = @($verifyPath, "--profile", $Profile, "--device", $Device)
    if ($DownloadModels) {
        $verifyArguments += @("--require-models", "--whisper", $WhisperModels)
    }
    Invoke-Native $VenvPython $verifyArguments

    Write-Host ""
    Write-Host "Installation complete."
    Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
    Write-Host "Verification log: $LogPath"
} finally {
    Pop-Location
    Stop-Transcript | Out-Null
}
