$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) { throw "Project virtual environment is missing: $PythonExe. Run .\setup_environment.ps1 first." }
& $PythonExe (Join-Path $ProjectRoot "xvf_test_runner.py") baseline --config (Join-Path $ProjectRoot "config.json")
if ($LASTEXITCODE -ne 0) { throw "Baseline failed with exit code $LASTEXITCODE" }
