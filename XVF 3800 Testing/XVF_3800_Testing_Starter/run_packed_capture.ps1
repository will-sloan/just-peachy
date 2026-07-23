param(
    [int]$Duration = 15,
    [string]$Label = "packed_six_channel_capture"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) { throw "Project virtual environment is missing: $PythonExe. Run .\setup_environment.ps1 first." }
Write-Host "Starting packed six-output recording for $Duration seconds..."
& $PythonExe (Join-Path $ProjectRoot "xvf_test_runner.py") packed-capture `
    --config ".\config.json" `
    --duration $Duration `
    --label $Label
if ($LASTEXITCODE -ne 0) { throw "Packed capture failed with exit code $LASTEXITCODE" }
