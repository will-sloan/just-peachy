param(
    [int]$Duration = 15,
    [string]$Label = "packed_asr_capture"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Project virtual environment is missing: $PythonExe. Run .\setup_environment.ps1 first." }
Write-Host "Starting automatic speech-recognition output recording for $Duration seconds..."
& $PythonExe (Join-Path $ProjectRoot "xvf_test_runner.py") asr-capture `
    --config (Join-Path $ProjectRoot "config.json") `
    --duration $Duration `
    --label $Label
if ($LASTEXITCODE -ne 0) { throw "ASR capture failed with exit code $LASTEXITCODE" }
