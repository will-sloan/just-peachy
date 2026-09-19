param([string]$Python = '', [string]$DataRoot = '', [string]$Models = '')
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $candidate = Join-Path (Split-Path $PSScriptRoot -Parent) '.edge-speech-env\python.exe'
    if (Test-Path -LiteralPath $candidate) { $Python = $candidate }
    elseif ($env:JUST_PEACHY_PYTHON) { $Python = $env:JUST_PEACHY_PYTHON }
    else { $Python = 'python' }
}
$launchArgs = @((Join-Path $PSScriptRoot 'main.py'), 'gui')
if ($DataRoot) { $launchArgs += @('--data-root', $DataRoot) }
if ($Models) { $launchArgs += @('--models', $Models) }
& $Python @launchArgs
if ($LASTEXITCODE -ne 0) { throw "Prototype stopped with exit code $LASTEXITCODE. Read START_PROTOTYPE.md." }
