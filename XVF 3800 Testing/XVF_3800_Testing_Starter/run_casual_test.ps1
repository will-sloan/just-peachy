param(
    [int]$Duration = 30,
    [string]$Profile = ".\test_profiles\casual_asr_vs_raw_mic0.json"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) { throw "Project virtual environment is missing: $PythonExe. Run .\setup_environment.ps1 first." }
if (-not [IO.Path]::IsPathRooted($Profile)) { $Profile = Join-Path $ProjectRoot $Profile }
if (-not (Test-Path $Profile)) { throw "Test profile not found: $Profile" }
& $PythonExe (Join-Path $ProjectRoot "xvf_test_runner.py") record `
    --config ".\config.json" `
    --profile $Profile `
    --duration $Duration `
    --live-plot
if ($LASTEXITCODE -ne 0) { throw "Casual recording failed with exit code $LASTEXITCODE" }
