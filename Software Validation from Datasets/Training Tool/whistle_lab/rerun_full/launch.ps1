param([ValidateSet('start','status','pause','resume','monitor')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$labRoot = (Get-Item -LiteralPath $PSScriptRoot).Parent.FullName
$repoRoot = (Get-Item -LiteralPath $labRoot).Parent.Parent.Parent.FullName
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
& $pythonExe (Join-Path $PSScriptRoot 'control.py') $Action
exit $LASTEXITCODE
