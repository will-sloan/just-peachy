param([ValidateSet('open', 'watch', 'start', 'pause', 'resume', 'status')][string]$Action = 'open')
$ErrorActionPreference = 'Stop'
$labRoot = $PSScriptRoot
$repoRoot = (Get-Item -LiteralPath $labRoot).Parent.Parent.Parent.FullName
$runRoot = Join-Path $repoRoot 'training\whistle_age_robust_v1'
$pythonExe = Join-Path $repoRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { $pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe' }
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
if ($Action -eq 'status') {
    Get-Content -LiteralPath (Join-Path $runRoot 'status.json')
    exit
}
Start-Process -FilePath $pythonExe -ArgumentList @(('"' + (Join-Path $labRoot 'supervisor.py') + '"')) -WorkingDirectory $labRoot -WindowStyle Hidden
if ($Action -in @('start', 'resume', 'pause')) {
    $controlPath = Join-Path $runRoot 'control.json'
    $state = @{ run_enabled = $true; paused = ($Action -eq 'pause'); changed_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
    if ($Action -ne 'pause') { $state.retry_requested = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
    $state | ConvertTo-Json | Set-Content -LiteralPath ($controlPath + '.new') -Encoding utf8
    Move-Item -LiteralPath ($controlPath + '.new') -Destination $controlPath -Force
}
if ($Action -eq 'open') { Start-Process 'http://127.0.0.1:8766' }
