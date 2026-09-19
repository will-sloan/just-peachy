[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PiHost,
    [Parameter(Mandatory=$true)][string]$UserName,
    [Parameter(Mandatory=$true)][string]$IdentityFile,
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$RemoteRoot,
    [Parameter(Mandatory=$true)][string]$RemoteDataRoot,
    [string]$Wheelhouse,
    [string]$Models,
    [switch]$Activate,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
if ($PiHost -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$' -or $UserName -notmatch '^[a-z_][a-z0-9_-]*$') { throw 'Use an explicit hostname/IPv4 and non-root Unix user; options/shell syntax are not accepted.' }
if ($UserName -eq 'root') { throw 'Run the application and its installer as a non-root account.' }
foreach ($value in @($RemoteRoot, $RemoteDataRoot)) {
    if ($value -notmatch '^/[A-Za-z0-9_ ./-]+$' -or $value -match '(^|/)\.\.(/|$)' -or $value -eq '/') { throw 'Remote paths must be explicit absolute paths without traversal or shell syntax.' }
}
function Q([string]$Value) { if ($Value.Contains("'") -or $Value.Contains("`n") -or $Value.Contains("`r")) { throw 'Unsupported quoting in remote token.' }; return "'$Value'" }
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
$keyPath = (Resolve-Path -LiteralPath $IdentityFile).Path
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$archiveStream = [System.IO.File]::OpenRead($archivePath)
try { $archiveHash = ([System.BitConverter]::ToString($sha256.ComputeHash($archiveStream))).Replace('-', '').ToLowerInvariant() }
finally { $archiveStream.Dispose(); $sha256.Dispose() }
$recipient = "$UserName@$PiHost"
$inbox = "$RemoteRoot/inbox/proto1-$([guid]::NewGuid().ToString('N'))"
$sshFlags = @('-i', $keyPath, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15')
$steps = [System.Collections.Generic.List[object]]::new()
function Add-Ssh([string]$Command) { $steps.Add(@{tool='ssh'; arguments=($sshFlags + @($recipient, $Command))}) }
function Add-Scp([string]$LocalPath, [string]$RemotePath, [switch]$Recursive) {
    $flags = @($sshFlags); if ($Recursive) { $flags += '-r' }
    $steps.Add(@{tool='scp'; arguments=($flags + @('--', $LocalPath, "${recipient}:$RemotePath"))})
}
# Probe before writes. python3.11 is a declared target requirement, not a guessed alias.
$probe = 'import json,os,platform,sys; assert platform.machine() in ("aarch64","arm64"), "Expected ARM64"; assert sys.version_info[:2] == (3,11), "Expected Python 3.11"; assert os.getuid()!=0, "Do not run as root"; print(json.dumps({"machine":platform.machine(),"python":platform.python_version(),"uid":os.getuid()}))'
Add-Ssh ("python3.11 -c " + (Q $probe))
Add-Ssh ("mkdir -p -- " + (Q $inbox))
Add-Scp $archivePath "$inbox/release.zip"
Add-Scp (Join-Path $PSScriptRoot 'release.py') "$inbox/release.py"
Add-Scp (Join-Path $PSScriptRoot 'install_pi.sh') "$inbox/install_pi.sh"
if ($Wheelhouse) { Add-Scp (Resolve-Path -LiteralPath $Wheelhouse).Path "$inbox/wheelhouse" -Recursive }
if ($Models) { Add-Scp (Resolve-Path -LiteralPath $Models).Path "$inbox/models" -Recursive }
$install = @('bash', "$inbox/install_pi.sh", '--archive', "$inbox/release.zip", '--sha256', $archiveHash, '--root', $RemoteRoot, '--data-root', $RemoteDataRoot)
if ($Wheelhouse) { $install += @('--wheelhouse', "$inbox/wheelhouse") }
if ($Models) { $install += @('--models', "$inbox/models") }
if ($Activate) { $install += '--activate' }
Add-Ssh (($install | ForEach-Object { Q $_ }) -join ' ')
if ($DryRun) {
    @{status='DRY_RUN_ONLY'; contacted_host=$false; expected_archive_sha256=$archiveHash; steps=$steps; activation_requested=[bool]$Activate} | ConvertTo-Json -Depth 8
    exit 0
}
foreach ($step in $steps) {
    & $step.tool @($step.arguments)
    if ($LASTEXITCODE -ne 0) { throw "$($step.tool) failed with exit code $LASTEXITCODE; activation was not continued." }
}
@{status='TRANSFER_AND_INSTALL_FINISHED'; host=$PiHost; activation_requested=[bool]$Activate; gui_started=$false} | ConvertTo-Json
