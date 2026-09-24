param([Parameter(Mandatory=$true)][string]$Archive, [Parameter(Mandatory=$true)][string]$FakeKey, [Parameter(Mandatory=$true)][string]$Output, [string]$Python = 'python')
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
# Reproduce the actual transferred helper set in isolation. This detects a
# missing runtime_lock dependency that a non-networked plan-only check misses.
$helperRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('jp-transfer-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $helperRoot | Out-Null
try {
    foreach ($step in $result.steps) {
        if ($step.tool -ne 'scp') { continue }
        $source = $step.arguments[$step.arguments.Count - 2]
        if ([System.IO.Path]::GetFileName($source) -in @('release.py', 'runtime_lock.py', 'install_pi.sh')) {
            Copy-Item -LiteralPath $source -Destination $helperRoot
        }
    }
    & $Python -B (Join-Path $helperRoot 'release.py') --help | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Transferred installer helper imports failed' }
} finally {
    $resolvedHelperRoot = [System.IO.Path]::GetFullPath($helperRoot)
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (-not $resolvedHelperRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe test cleanup path' }
    Remove-Item -LiteralPath $resolvedHelperRoot -Recurse -Force
}
$raw | Set-Content -LiteralPath $Output -Encoding UTF8
@{status='PASS'; powershell_parser='PASS'; transferred_helper_imports='PASS'; plan_steps=$result.steps.Count; contacted_host=$false} | ConvertTo-Json -Compress
