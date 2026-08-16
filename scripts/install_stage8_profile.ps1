[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("core-cuda", "extended-local", "onnx", "wenet", "wespeaker", "credential-diarization", "edge-cpu", "moonshine-edge")]
    [string]$Profile,

    [string]$Python = "",
    [switch]$DownloadModels,
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$EnvironmentRoot = Join-Path $ProjectRoot ".stage8-envs"
$EnvironmentPath = Join-Path $EnvironmentRoot $Profile
$EnvironmentPython = Join-Path $EnvironmentPath "Scripts\python.exe"
$LogRoot = Join-Path $ProjectRoot ".install-logs\stage8"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogRoot "$($Profile)_$Timestamp.log"

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

function Resolve-BasePython {
    if ($Python) {
        return (Get-Command $Python -ErrorAction Stop).Source
    }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3.12 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return $launcher.Source
        }
    }
    $candidate = Get-Command python -ErrorAction Stop
    return $candidate.Source
}

function New-IsolatedEnvironment {
    $basePython = Resolve-BasePython
    if ((Split-Path -Leaf $basePython) -ieq "py.exe") {
        Invoke-Native $basePython @("-3.12", "-m", "venv", $EnvironmentPath)
    } else {
        Invoke-Native $basePython @("-m", "venv", $EnvironmentPath)
    }
}

function Model-BootstrapArguments {
    switch ($Profile) {
        "core-cuda" {
            return @(
                "--whisper", "tiny,base,small", "--speechbrain-ecapa", "--silero",
                "--device", "cuda"
            )
        }
        "extended-local" { return @("--faster-whisper-tiny", "--vosk-asr") }
        "onnx" {
            return @(
                "--sherpa-asr", "--sherpa-vad", "--sherpa-speaker-embedding", "--sherpa-diarization",
                "--sherpa-libri-giga", "--sherpa-streaming-20m", "--campplus", "--eres2net-base"
            )
        }
        "wenet" { return @("--wenet-asr") }
        "wespeaker" { return @("--wespeaker") }
        "credential-diarization" {
            if (-not $env:PYANNOTE_LICENSE_ACCEPTED -or -not $env:PYANNOTE_AUTH_TOKEN) {
                throw "pyannote model bootstrap requires PYANNOTE_LICENSE_ACCEPTED=1 and PYANNOTE_AUTH_TOKEN. Secret values are never logged."
            }
            return @("--pyannote", "--hf-token-env", "PYANNOTE_AUTH_TOKEN")
        }
        "edge-cpu" {
            return @(
                "--whisper", "base",
                "--silero",
                "--fsmn-vad",
                "--device", "cpu"
            )
        }
        "moonshine-edge" {
            return @("--moonshine-streaming", "tiny,small,medium")
        }
        default { return @() }
    }
}

New-Item -ItemType Directory -Path $EnvironmentRoot -Force | Out-Null
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
Start-Transcript -Path $LogPath -Force | Out-Null
Push-Location $ProjectRoot
try {
    if ($Recreate -and (Test-Path -LiteralPath $EnvironmentPath)) {
        $resolvedEnvironment = [System.IO.Path]::GetFullPath($EnvironmentPath)
        $expectedPrefix = $EnvironmentRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
        if (-not $resolvedEnvironment.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove an environment outside .stage8-envs: $resolvedEnvironment"
        }
        Remove-Item -LiteralPath $resolvedEnvironment -Recurse -Force
    }
    if (-not (Test-Path -LiteralPath $EnvironmentPython -PathType Leaf)) {
        New-IsolatedEnvironment
    }

    if ($Profile -eq "core-cuda") {
        Invoke-Native $EnvironmentPython @(
            "-m", "pip", "install",
            "torch==2.11.0", "torchaudio==2.11.0",
            "--index-url", "https://download.pytorch.org/whl/cu128"
        )
    } elseif ($Profile -in @("edge-cpu", "moonshine-edge")) {
        Invoke-Native $EnvironmentPython @(
            "-m", "pip", "install",
            "torch==2.11.0", "torchaudio==2.11.0",
            "--index-url", "https://download.pytorch.org/whl/cpu"
        )
    }
    $RequirementsPath = Join-Path $ProjectRoot "requirements\stage8\$Profile.txt"
    Invoke-Native $EnvironmentPython @("-m", "pip", "install", "-r", $RequirementsPath)
    if ($Profile -eq "wenet") {
        # WeNet v3.1.0 declares the obsolete PySoundFile distribution, which
        # can overwrite the modern `soundfile` module. Restore the repository
        # pin after source installation without changing its dependency graph.
        Invoke-Native $EnvironmentPython @(
            "-m", "pip", "install", "--force-reinstall", "--no-deps",
            "soundfile==0.13.1"
        )
    }
    if ($Profile -eq "wespeaker") {
        $WeSpeakerPackage = Join-Path $ProjectRoot "requirements\stage8\wespeaker-package.txt"
        Invoke-Native $EnvironmentPython @(
            "-m", "pip", "install", "--no-deps", "-r", $WeSpeakerPackage
        )
    }
    if ($Profile -eq "wespeaker") {
        $CheckOutput = @(& $EnvironmentPython -m pip check 2>&1)
        $Unexpected = @(
            $CheckOutput | Where-Object {
                $_ -and $_ -notmatch "wespeaker 0\.0\.0 has requirement hdbscan==0\.8\.37, but you have hdbscan 0\.8\.44\."
            }
        )
        if ($Unexpected.Count -gt 0) {
            throw "WeSpeaker profile has unexpected pip-check failures: $($Unexpected -join '; ')"
        }
        Write-Warning "Accepted isolated WeSpeaker metadata mismatch: hdbscan 0.8.44 replaces the unavailable 0.8.37 Python 3.12 build."
    } else {
        Invoke-Native $EnvironmentPython @("-m", "pip", "check")
    }

    if ($DownloadModels) {
        $bootstrap = Join-Path $ProjectRoot "scripts\bootstrap_models.py"
        $arguments = @($bootstrap, "--cache-root", (Join-Path $ProjectRoot "models\cache")) + (Model-BootstrapArguments)
        if ($arguments.Count -gt 3) {
            Invoke-Native $EnvironmentPython $arguments
        }
    }

    $freezePath = Join-Path $EnvironmentPath "environment.freeze.txt"
    & $EnvironmentPython -m pip freeze --all | Set-Content -LiteralPath $freezePath -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "pip freeze failed for $Profile"
    }
    Write-Host "[PASS] Stage 8 profile prepared: $Profile"
    Write-Host "Python: $EnvironmentPython"
    Write-Host "Freeze: $freezePath"
    Write-Host "Log: $LogPath"
} finally {
    Pop-Location
    Stop-Transcript | Out-Null
}
