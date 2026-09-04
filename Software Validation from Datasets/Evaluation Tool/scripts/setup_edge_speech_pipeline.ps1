param(
    [string]$PythonVersion = "3.11"
)

$ErrorActionPreference = "Stop"
$EvaluationRoot = Split-Path -Parent $PSScriptRoot
$RepositoryRoot = Split-Path -Parent (Split-Path -Parent $EvaluationRoot)
$EnvironmentPath = Join-Path $RepositoryRoot ".edge-speech-env"
$Requirements = Join-Path $EvaluationRoot "requirements-edge-speech-windows.txt"

function Find-EnvironmentPython {
    @(
        (Join-Path $EnvironmentPath "python.exe"),
        (Join-Path $EnvironmentPath "Scripts\python.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

$EnvironmentPython = Find-EnvironmentPython
if (-not $EnvironmentPython) {
    $Conda = Get-Command conda -ErrorAction SilentlyContinue
    if ($Conda) {
        & conda create --prefix $EnvironmentPath "python=$PythonVersion" -y
    } else {
        $Python = Get-Command py -ErrorAction SilentlyContinue
        if (-not $Python) {
            throw "Install Anaconda/Miniconda or Python $PythonVersion, then rerun this setup."
        }
        & py "-$PythonVersion" -m venv $EnvironmentPath
    }
    $EnvironmentPython = Find-EnvironmentPython
}

if (-not $EnvironmentPython) {
    throw "The edge-speech environment was created but python.exe was not found."
}
& $EnvironmentPython -m pip install --upgrade pip
& $EnvironmentPython -m pip install -r $Requirements
Set-Location -LiteralPath $EvaluationRoot
& $EnvironmentPython -m app.edge_speech_pipeline validate
