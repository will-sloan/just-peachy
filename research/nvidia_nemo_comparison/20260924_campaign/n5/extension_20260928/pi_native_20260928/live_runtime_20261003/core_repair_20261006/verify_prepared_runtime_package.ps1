param(
  [Parameter(Mandatory)][string]$BuildRoot,
  [Parameter(Mandatory)][string]$ManifestSha256,
  [Parameter(Mandatory)][string]$ArchiveSha256,
  [Parameter(Mandatory)][string]$SourceReviewSha256,
  [Parameter(Mandatory)][string]$Version
)
# See README_VERIFY_PREPARED_RUNTIME_PACKAGE.md. Host code artifact verification only.
$ErrorActionPreference='Stop'
$jpProcess=[Diagnostics.Process]::GetCurrentProcess()
$jpProcess.ProcessorAffinity=[IntPtr]16384
$jpPrivate='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation'
$jpOutput=Join-Path $jpPrivate ('independent-package-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($jpOutput)
function Put-New([string]$Path,[byte[]]$Bytes) {
  $s=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try {$s.Write($Bytes,0,$Bytes.Length);$s.Flush($true)} finally {$s.Dispose()}
  if((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes))) {throw 'Independent written-byte hash differs'}
}
function Hash([string]$Path) {(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Json-New([string]$Path,$Value) {Put-New $Path ([Text.Encoding]::UTF8.GetBytes(($Value|ConvertTo-Json -Depth 12 -Compress)))}
$jpStamp=$jpProcess.StartTime.ToUniversalTime().ToFileTimeUtc()
$jpOwner=@{schema='just-peachy.host-registered-owner.v1';pid=$PID;cpu=14;affinity_mask=16384;creation_filetime=$jpStamp;create_time=($jpStamp-116444736000000000)/10000000}
Json-New ($jpOutput+'/REGISTERED_OWNER.json') $jpOwner
if($Version -notmatch '^\d{2}$' -or @($ManifestSha256,$ArchiveSha256,$SourceReviewSha256).Where({$_ -notmatch '^[0-9a-f]{64}$'}).Count) {throw 'Exact version and SHA256 pins required'}
$jpBuild=[IO.Path]::GetFullPath($BuildRoot)
if([IO.Path]::GetDirectoryName($jpBuild) -ne [IO.Path]::GetFullPath($jpPrivate)) {throw 'Exact private build parent required'}
if((Get-PSDrive C).Free -lt 50GB -or (Get-PSDrive G).Free -lt 75GB) {throw 'Physical host free-space floor'}
foreach($jpSource in @($PSCommandPath,($PSScriptRoot+'/README_VERIFY_PREPARED_RUNTIME_PACKAGE.md'))) {
  $jpBytes=[IO.File]::ReadAllBytes($jpSource)
  foreach($jpSuffix in 'backup','restore') {Put-New ($jpOutput+'/'+[IO.Path]::GetFileName($jpSource)+'.'+$jpSuffix) $jpBytes}
}
$jpArchive=$jpBuild+'/field-runtime-v29-build-'+$Version+'-prepared.tar.gz'
if((Hash $jpArchive) -ne $ArchiveSha256 -or (Hash ($jpBuild+'/package/PACKAGE_MANIFEST.json')) -ne $ManifestSha256 -or (Hash ($jpBuild+'/SOURCE_DIFF_REVIEW.json')) -ne $SourceReviewSha256) {throw 'Prepared package input pin drift'}
$jpBuilder=Get-Content -LiteralPath ($jpBuild+'/REGISTERED_OWNER.json') -Raw|ConvertFrom-Json
if(Get-Process -Id $jpBuilder.pid -ErrorAction SilentlyContinue) {throw 'Builder PID remains present'}
$jpRestore=$jpOutput+'/expanded-restore'
[void][IO.Directory]::CreateDirectory($jpRestore)
$jpNames=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$jpBytesTotal=[long]0
$jpArchiveStream=[IO.File]::OpenRead($jpArchive)
$jpGzip=[IO.Compression.GZipStream]::new($jpArchiveStream,[IO.Compression.CompressionMode]::Decompress)
$jpTar=[System.Formats.Tar.TarReader]::new($jpGzip)
try {
  while($null -ne ($jpEntry=$jpTar.GetNextEntry())) {
    $jpName=$jpEntry.Name
    if($jpEntry.EntryType -notin @([System.Formats.Tar.TarEntryType]::RegularFile,[System.Formats.Tar.TarEntryType]::V7RegularFile) -or $jpName.Contains('\') -or $jpName.StartsWith('/') -or @($jpName.Split('/')).Where({$_ -in @('','.','..')}).Count -or !$jpNames.Add($jpName)) {throw 'Unsafe or duplicate archive member'}
    if($jpNames.Count -gt 512 -or $jpEntry.Length -gt 2MB -or ($jpBytesTotal+$jpEntry.Length) -gt 32MB) {throw 'Bounded code archive extent exceeded'}
    $jpDestination=[IO.Path]::GetFullPath((Join-Path $jpRestore $jpName))
    if(!$jpDestination.StartsWith([IO.Path]::GetFullPath($jpRestore)+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {throw 'Archive target escapes fresh restore'}
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($jpDestination))
    $jpMemory=[IO.MemoryStream]::new()
    try {$jpEntry.DataStream.CopyTo($jpMemory);$jpRaw=$jpMemory.ToArray()} finally {$jpMemory.Dispose()}
    if($jpRaw.LongLength -ne $jpEntry.Length) {throw 'Tar member extent differs'}
    Put-New $jpDestination $jpRaw
    if((Hash $jpDestination) -ne (Hash ($jpBuild+'/package/'+$jpName))) {throw 'Independent expanded member differs'}
    $jpBytesTotal+=$jpEntry.Length
  }
} finally {$jpTar.Dispose();$jpGzip.Dispose();$jpArchiveStream.Dispose()}
$jpFiles=@(Get-ChildItem -LiteralPath ($jpBuild+'/package') -Recurse -File)
if($jpFiles.Count -ne $jpNames.Count) {throw 'Prepared and restored membership differs'}
foreach($jpFile in $jpFiles) {if(!$jpNames.Contains([IO.Path]::GetRelativePath($jpBuild+'/package',$jpFile.FullName).Replace('\','/'))) {throw 'Missing expanded member'}}
$jpSources=Get-Content -LiteralPath ($jpBuild+'/PREPARED_SOURCE_CLOSED.json') -Raw|ConvertFrom-Json
foreach($jpPin in $jpSources.inputs.PSObject.Properties) {
  foreach($jpPath in @($jpPin.Value.path,($jpBuild+'/prepared-source/backup/'+$jpPin.Name),($jpBuild+'/prepared-source/restore/'+$jpPin.Name))) {if((Hash $jpPath) -ne $jpPin.Value.sha256) {throw 'Actual source/backup/restore drift'}}
}
$jpReceipt=@{schema=('just-peachy.core-package'+$Version+'-independent-closure.v1');owner=$jpBuilder;validator_owner=$jpOwner;builder_natural_exit_code=0;builder_os_process_absent=$true;archive_members_readback=$jpNames.Count;archive_expanded_bytes=$jpBytesTotal;independent_expanded_restore_exact=$true;source_inputs=@($jpSources.inputs.PSObject.Properties).Count;source_backups_and_independent_restores_exact=$true;current_sources_unchanged=$true;manifest_sha256=$ManifestSha256;archive_sha256=$ArchiveSha256;source_review_sha256=$SourceReviewSha256;validator_sha256=(Hash $PSCommandPath);native_action=$false;closed_utc=[DateTime]::UtcNow.ToString('o')}
Json-New ($jpOutput+'/INDEPENDENT_CLOSURE.json') $jpReceipt
Put-New ($jpBuild+'/INDEPENDENT_CLOSURE.json') ([IO.File]::ReadAllBytes($jpOutput+'/INDEPENDENT_CLOSURE.json'))
@{output=$jpOutput;archive_members_readback=$jpNames.Count;archive_expanded_bytes=$jpBytesTotal;closure_sha256=(Hash ($jpBuild+'/INDEPENDENT_CLOSURE.json'));native_action=$false}|ConvertTo-Json -Compress
