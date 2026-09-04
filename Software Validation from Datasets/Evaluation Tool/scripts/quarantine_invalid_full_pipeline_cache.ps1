[CmdletBinding()]
param(
    [string]$Workspace,
    [string]$CacheRoot,
    [string]$QuarantineRoot,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($Workspace)) {
    $Workspace = Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
}
$Workspace = [IO.Path]::GetFullPath($Workspace)
if ([string]::IsNullOrWhiteSpace($CacheRoot)) {
    $CacheRoot = Join-Path $ToolRoot 'JustPeachyResults\full_pipeline\_shared_cache'
}
if ([string]::IsNullOrWhiteSpace($QuarantineRoot)) {
    $QuarantineRoot = Join-Path $Workspace 'cache_quarantine'
}

$ResolvedCacheRoot = (Resolve-Path -LiteralPath $CacheRoot).Path.TrimEnd('\')
$ResolvedWorkspace = (Resolve-Path -LiteralPath $Workspace).Path.TrimEnd('\')
$ResolvedQuarantineRoot = [IO.Path]::GetFullPath($QuarantineRoot).TrimEnd('\')
$CachePrefix = $ResolvedCacheRoot + '\'
$WorkspacePrefix = $ResolvedWorkspace + '\'
if (-not $ResolvedCacheRoot.StartsWith($ToolRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Cache root is outside the evaluation tool: $ResolvedCacheRoot"
}
if (-not $ResolvedQuarantineRoot.StartsWith($WorkspacePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Quarantine root must remain inside the H2 workspace: $ResolvedQuarantineRoot"
}
if ([IO.Path]::GetPathRoot($ResolvedCacheRoot) -ne 'C:\' -or
    [IO.Path]::GetPathRoot($ResolvedQuarantineRoot) -ne 'C:\') {
    throw 'Cache and quarantine roots must remain on C:.'
}

$Ripgrep = (Get-Command rg -ErrorAction Stop).Source
$CandidateRows = @(
    & $Ripgrep --text --files-without-match --glob '*.json' --max-count 1 '^\{' $ResolvedCacheRoot
)
if ($LASTEXITCODE -notin @(0,1)) {
    throw "Cache candidate scan failed with exit code $LASTEXITCODE"
}

$Invalid = @()
foreach ($CandidateRow in $CandidateRows) {
    if ([string]::IsNullOrWhiteSpace($CandidateRow)) { continue }
    $ResolvedPath = [IO.Path]::GetFullPath($CandidateRow)
    if (-not $ResolvedPath.StartsWith($CachePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Candidate escaped the verified cache root: $ResolvedPath"
    }
    $Bytes = [IO.File]::ReadAllBytes($ResolvedPath)
    try {
        $Parsed = [Text.Encoding]::UTF8.GetString($Bytes) | ConvertFrom-Json
        if ($null -eq $Parsed) {
            throw 'JSON parser returned no document'
        }
        continue
    }
    catch {
        $RelativePath = $ResolvedPath.Substring($CachePrefix.Length)
        $Hash = (Get-FileHash -LiteralPath $ResolvedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $AllZero = $true
        foreach ($Byte in $Bytes) {
            if ($Byte -ne 0) { $AllZero = $false; break }
        }
        $Invalid += [ordered]@{
            relative_path = $RelativePath.Replace('\', '/')
            source_path = $ResolvedPath
            size_bytes = [int64]$Bytes.LongLength
            sha256 = $Hash
            all_zero = $AllZero
            parse_error = $_.Exception.Message
            last_write_utc = (Get-Item -LiteralPath $ResolvedPath).LastWriteTimeUtc.ToString('o')
        }
    }
}

$InventoryText = @(
    $Invalid |
        Sort-Object { $_.relative_path } |
        ForEach-Object { "$($_.relative_path)|$($_.size_bytes)|$($_.sha256)" }
) -join "`n"
$Hasher = [Security.Cryptography.SHA256]::Create()
try {
    $InventoryHash = [BitConverter]::ToString(
        $Hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($InventoryText))
    ).Replace('-', '').ToLowerInvariant()
}
finally {
    $Hasher.Dispose()
}
$SetId = "invalid_cache_$($InventoryHash.Substring(0,16))"
$SetRoot = Join-Path $ResolvedQuarantineRoot $SetId
$PlanPath = Join-Path $SetRoot 'QUARANTINE_PLAN.json'
$ReceiptPath = Join-Path $SetRoot 'QUARANTINE_RECEIPT.json'
$InvalidBytes = [int64]0
foreach ($Entry in $Invalid) {
    $InvalidBytes += [int64]$Entry.size_bytes
}
$Plan = [ordered]@{
    schema_version = 'full-pipeline-invalid-cache-quarantine-plan.v1'
    set_id = $SetId
    generated_at = [DateTimeOffset]::Now.ToString('o')
    cache_root = $ResolvedCacheRoot
    quarantine_root = $SetRoot
    inventory_sha256 = $InventoryHash
    candidate_count = $CandidateRows.Count
    invalid_count = $Invalid.Count
    invalid_bytes = $InvalidBytes
    all_zero_count = @($Invalid | Where-Object all_zero).Count
    entries = @($Invalid | Sort-Object { $_.relative_path })
}

if (-not $Apply) {
    [pscustomobject]@{
        Status = 'DRY_RUN_PASS'
        SetId = $SetId
        CandidateCount = $CandidateRows.Count
        InvalidCount = $Invalid.Count
        InvalidBytes = $Plan.invalid_bytes
        AllZeroCount = $Plan.all_zero_count
        PlanPath = $PlanPath
        KnownFailurePresent = @($Invalid | Where-Object {
            $_.relative_path -eq '99/998360d8f87cc4485cafc90e1f530405d9220701a798b4347c4ef59ce2774f4c.json'
        }).Count -eq 1
    } | ConvertTo-Json
    exit 0
}

if ($Invalid.Count -eq 0) {
    [pscustomobject]@{ Status = 'NO_INVALID_CACHE_FILES'; InvalidCount = 0 } |
        ConvertTo-Json
    exit 0
}

New-Item -ItemType Directory -Path $SetRoot -Force | Out-Null
$Plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $PlanPath -Encoding UTF8
$Moved = 0
foreach ($Entry in $Plan.entries) {
    $Source = [IO.Path]::GetFullPath([string]$Entry.source_path)
    if (-not $Source.StartsWith($CachePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Planned source escaped the verified cache root: $Source"
    }
    $Destination = Join-Path (Join-Path $SetRoot 'files') ([string]$Entry.relative_path)
    $ResolvedDestination = [IO.Path]::GetFullPath($Destination)
    if (-not $ResolvedDestination.StartsWith($SetRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Planned destination escaped the quarantine set: $ResolvedDestination"
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $ResolvedDestination) -Force | Out-Null
    Move-Item -LiteralPath $Source -Destination $ResolvedDestination
    $MovedHash = (Get-FileHash -LiteralPath $ResolvedDestination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($MovedHash -ne [string]$Entry.sha256) {
        throw "Quarantined cache checksum differs: $ResolvedDestination"
    }
    $Moved += 1
}

$Receipt = [ordered]@{
    schema_version = 'full-pipeline-invalid-cache-quarantine-receipt.v1'
    status = 'QUARANTINED'
    set_id = $SetId
    completed_at = [DateTimeOffset]::Now.ToString('o')
    plan_path = $PlanPath
    plan_sha256 = (Get-FileHash -LiteralPath $PlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
    inventory_sha256 = $InventoryHash
    moved_count = $Moved
    moved_bytes = $Plan.invalid_bytes
    recoverable = $true
    scientific_results_modified = $false
    valid_cache_entries_modified = $false
}
$Receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
[pscustomobject]@{
    Status = 'QUARANTINED'
    SetId = $SetId
    MovedCount = $Moved
    MovedBytes = $Plan.invalid_bytes
    PlanPath = $PlanPath
    ReceiptPath = $ReceiptPath
    Recoverable = $true
} | ConvertTo-Json
