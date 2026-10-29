param([ValidateSet('watch','open','pause','resume','status','prepare')][string]$Action = 'watch')
$ErrorActionPreference = 'Stop'
$labRoot = (Get-Item -LiteralPath $PSScriptRoot).Parent.FullName
$repoRoot = (Get-Item -LiteralPath $labRoot).Parent.Parent.Parent.FullName
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if ($Action -in @('pause','resume','status','prepare')) {
    & $pythonExe (Join-Path $PSScriptRoot 'campaign.py') --action $Action
    exit $LASTEXITCODE
}
$pythonWindowless = Join-Path $repoRoot '.venv\Scripts\pythonw.exe'
Start-Process -FilePath $pythonWindowless -ArgumentList @(('"' + (Join-Path $PSScriptRoot 'campaign.py') + '"'), '--action', 'watch') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
if ($Action -eq 'open') { Start-Process 'http://127.0.0.1:8767/' }
