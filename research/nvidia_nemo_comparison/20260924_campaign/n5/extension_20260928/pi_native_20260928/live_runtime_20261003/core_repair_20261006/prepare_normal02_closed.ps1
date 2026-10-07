<# Exact closed-normal02 payload/source preparation. README_NORMAL02_CLOSED.md. #>
param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$taskProcess=[System.Diagnostics.Process]::GetCurrentProcess()
$taskProcess.ProcessorAffinity=[IntPtr]16384
$taskOwner=[ordered]@{schema='just-peachy.host-registered-owner.v1';pid=$PID;cpu=14;affinity_mask=16384;creation_filetime=$taskProcess.StartTime.ToUniversalTime().ToFileTimeUtc();create_time=([DateTimeOffset]$taskProcess.StartTime.ToUniversalTime()).ToUnixTimeMilliseconds()/1000.0}
$taskBase='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation'
$taskOut=[System.IO.Path]::GetFullPath($OutputDirectory)
$taskPrefix=[System.IO.Path]::GetFullPath($taskBase)+[System.IO.Path]::DirectorySeparatorChar
if (-not $taskOut.StartsWith($taskPrefix,[StringComparison]::OrdinalIgnoreCase) -or [System.IO.Directory]::Exists($taskOut) -or [System.IO.File]::Exists($taskOut)) {throw 'Fresh exact private audit-preparation child required'}
[System.IO.Directory]::CreateDirectory($taskOut)|Out-Null
$taskStarted=[Diagnostics.Stopwatch]::StartNew();$script:taskWritten=0
$taskUtf8=[System.Text.UTF8Encoding]::new($false,$true)
function Write-Exact([string]$Name,[byte[]]$Bytes) {
    if ($script:taskWritten+$Bytes.Length -gt 1MB -or $taskStarted.Elapsed.TotalSeconds -gt 60) {throw 'Finite source preparation scope exceeded'}
    $taskDest=Join-Path $taskOut $Name
    $taskStream=[System.IO.FileStream]::new($taskDest,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
    try {$taskStream.Write($Bytes,0,$Bytes.Length);$taskStream.Flush($true)} finally {$taskStream.Dispose()}
    $taskRestore=[System.IO.File]::ReadAllBytes($taskDest)
    if ([Convert]::ToBase64String($taskRestore) -cne [Convert]::ToBase64String($Bytes)) {throw 'Independent written-byte readback differs'}
    $script:taskWritten+=$Bytes.Length
}
function Json-Bytes($Value) {$taskUtf8.GetBytes(($Value|ConvertTo-Json -Depth 16 -Compress))}
Write-Exact 'REGISTERED_OWNER.json' (Json-Bytes $taskOwner)
# Source reads occur only after the exact host owner is registered.
$taskDrives=@{C=50GB;G=75GB}
foreach ($taskLetter in $taskDrives.Keys) {if ((Get-PSDrive $taskLetter).Free -lt $taskDrives[$taskLetter]+8MB) {throw 'Existing C50/G75 physical reserve required'}}
$taskSources=@('inspect_normal02_closed.py','prepare_normal02_closed.ps1','README_NORMAL02_CLOSED.md')
$taskPins=@()
foreach ($taskName in $taskSources) {
    $taskPath=Join-Path $PSScriptRoot $taskName
    $taskInfo=Get-Item -LiteralPath $taskPath
    if ($taskInfo.PSIsContainer -or $taskInfo.Length -gt 65536 -or ($taskInfo.Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'Bounded ordinary source required'}
    $taskRaw=[IO.File]::ReadAllBytes($taskPath)
    $taskHash=(Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($taskRaw.Length -ne $taskInfo.Length) {throw 'Source size changed'}
    Write-Exact ($taskName+'.backup') $taskRaw
    Write-Exact ($taskName+'.restore') $taskRaw
    if ((Get-FileHash -LiteralPath $taskPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $taskHash) {throw 'Original source changed during preservation'}
    $taskPins+=@{source=$taskPath;bytes=$taskRaw.Length;sha256=$taskHash;backup=(Join-Path $taskOut ($taskName+'.backup'));restore=(Join-Path $taskOut ($taskName+'.restore'))}
    if ($taskName -eq 'inspect_normal02_closed.py') {Write-Exact 'ACTION.py' $taskRaw}
}
$taskPayload=[ordered]@{schema='just-peachy.normal02-closed-inspection.v1';package_manifest_sha256='5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f';boot_id='e60e67c2-f3f5-4b8b-8eab-2613df2de37e';launch_id='1c846cf0acba464485dc5222a6158529';session_id='2013dbd12ca74e979d9b809c41e3a90f';expires_unix=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()+600}
Write-Exact 'PAYLOAD.json' (Json-Bytes $taskPayload)
Write-Exact 'SOURCE_CLOSED.json' (Json-Bytes @{schema='just-peachy.normal02-closed-source.v1';owner=$taskOwner;source_pins=$taskPins;independent_backups_and_restores=$true;source_unchanged=$true;native_action=$false;maximum_bytes=1MB;maximum_seconds=60;prepared_bytes=$script:taskWritten;closed_unix=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()})
[ordered]@{status='PREPARED_ONLY';output=$taskOut;action=(Join-Path $taskOut 'ACTION.py');payload=(Join-Path $taskOut 'PAYLOAD.json');source_closed_sha256=(Get-FileHash -LiteralPath (Join-Path $taskOut 'SOURCE_CLOSED.json') -Algorithm SHA256).Hash.ToLowerInvariant();native_executed=$false}|ConvertTo-Json -Compress
