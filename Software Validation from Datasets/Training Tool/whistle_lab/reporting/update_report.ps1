# Append new completed evidence to the Word report; never launches training.
$ErrorActionPreference = 'Stop'
$runtimePython = 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) { throw 'Bundled document Python is unavailable. Resolve it with the Codex workspace dependency loader.' }
$scriptPath = Join-Path $PSScriptRoot 'report.py'
& $runtimePython $scriptPath
if ($LASTEXITCODE -ne 0) { throw ('Word reporting failed with exit code ' + $LASTEXITCODE) }
