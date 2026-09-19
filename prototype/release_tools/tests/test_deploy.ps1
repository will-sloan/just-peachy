param([Parameter(Mandatory=$true)][string]$Archive, [Parameter(Mandatory=$true)][string]$FakeKey, [Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'deploy_pi.ps1'
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$null, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
$raw = & $scriptPath -PiHost 'test.invalid' -UserName 'fixture' -IdentityFile $FakeKey -Archive $Archive -RemoteRoot '/home/fixture/install root' -RemoteDataRoot '/home/fixture/private data' -Activate -DryRun
$result = ($raw | Out-String) | ConvertFrom-Json
if ($result.status -ne 'DRY_RUN_ONLY' -or $result.contacted_host -ne $false -or $result.steps.Count -lt 5) { throw 'Unexpected dry-run outcome' }
foreach ($step in $result.steps) {
    if (-not ($step.arguments -contains 'StrictHostKeyChecking=yes')) { throw 'Missing host-key protection' }
}
$raw | Set-Content -LiteralPath $Output -Encoding UTF8
@{status='PASS'; powershell_parser='PASS'; plan_steps=$result.steps.Count; contacted_host=$false} | ConvertTo-Json -Compress
