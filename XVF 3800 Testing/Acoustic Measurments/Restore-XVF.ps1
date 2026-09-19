param(
    [string]$Destination = (Join-Path $PSScriptRoot 'XVF_Restored'),
    [string]$ArchivePath = (Join-Path $PSScriptRoot 'XVF_DATA.zip'),
    [string]$ManifestPath = (Join-Path $PSScriptRoot 'RESTORE_MANIFEST.json')
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$TargetRoot = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
if (Test-Path -LiteralPath $TargetRoot) { throw 'Destination already exists. Choose a NEW destination; existing data will not be overwritten.' }
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Manifest.format -ne 'XVF lossless deduplicated ZIP v1') { throw 'Unsupported transfer format.' }
function File-Sha256([string]$FilePath) {
    $Hasher = [Security.Cryptography.SHA256]::Create()
    $Stream = [IO.File]::OpenRead($FilePath)
    try { return ([BitConverter]::ToString($Hasher.ComputeHash($Stream))).Replace('-', '').ToLowerInvariant() }
    finally { $Stream.Dispose(); $Hasher.Dispose() }
}
function Target-Path([string]$Relative) {
    if ($Relative -notmatch '^(project|reference_documents)(/|$)' -or $Relative -match '(^|/)[.][.](/|$)' -or $Relative.Contains(':') -or $Relative.Contains('\')) {
        throw "Invalid relative path: $Relative"
    }
    $ResolvedTarget = [IO.Path]::GetFullPath((Join-Path $TargetRoot $Relative))
    if (-not $ResolvedTarget.StartsWith($TargetRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes restoration directory.' }
    return $ResolvedTarget
}
$SeenPaths = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($Row in $Manifest.files) {
    $null = Target-Path $Row.path
    if (-not $SeenPaths.Add($Row.path)) { throw "Duplicate restoration path: $($Row.path)" }
    if ($Row.sha256 -notmatch '^[0-9a-f]{64}$' -or $Row.bytes -lt 0) { throw 'Invalid file hash or size.' }
}
foreach ($Dir in $Manifest.directories) { $null = Target-Path $Dir }
$DriveInfo = New-Object System.IO.DriveInfo ([IO.Path]::GetPathRoot($TargetRoot))
if ($DriveInfo.AvailableFreeSpace -lt ([long]$Manifest.logical_bytes + 268435456)) { throw 'Not enough free space to restore the complete data.' }
$Zip = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($ArchivePath))
$Canonical = @{}
$Verified = 0
try {
    New-Item -ItemType Directory -Path $TargetRoot | Out-Null
    foreach ($Dir in $Manifest.directories) { [IO.Directory]::CreateDirectory((Target-Path $Dir)) | Out-Null }
    foreach ($Row in $Manifest.files) {
        $Target = Target-Path $Row.path
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Target)) | Out-Null
        if ($Canonical.ContainsKey($Row.sha256)) {
            Copy-Item -LiteralPath $Canonical[$Row.sha256] -Destination $Target
        } else {
            $Entry = $Zip.GetEntry('objects/' + $Row.sha256)
            if ($null -eq $Entry -or $Entry.Length -ne $Row.bytes) { throw "Missing or wrong-size archive object: $($Row.path)" }
            $InputStream = $Entry.Open()
            try {
                $OutputStream = [IO.File]::Open($Target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
                try { $InputStream.CopyTo($OutputStream) } finally { $OutputStream.Dispose() }
            } finally { $InputStream.Dispose() }
        }
        if ((Get-Item -LiteralPath $Target).Length -ne $Row.bytes -or (File-Sha256 $Target) -ne $Row.sha256) {
            throw "Restoration verification failed: $($Row.path)"
        }
        $Canonical[$Row.sha256] = $Target
        [IO.File]::SetLastWriteTimeUtc($Target, [DateTimeOffset]::FromUnixTimeMilliseconds([long][Math]::Floor($Row.mtime_ns / 1000000)).UtcDateTime)
        $Verified++
        if (($Verified % 500) -eq 0) { Write-Host "Restored and verified $Verified / $($Manifest.files.Count) files" }
    }
    @{status='COMPLETE';verified_files=$Verified;restored_bytes=$Manifest.logical_bytes;completed_utc=[DateTime]::UtcNow.ToString('o');source_archive=$ArchivePath;destination=$TargetRoot} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $TargetRoot 'RESTORE_VERIFICATION.json') -Encoding UTF8
    Write-Host "SUCCESS: restored and SHA-256 verified all $Verified files at $TargetRoot"
} finally { $Zip.Dispose() }
