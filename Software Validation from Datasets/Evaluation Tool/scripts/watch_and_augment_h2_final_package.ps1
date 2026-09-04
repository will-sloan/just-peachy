[CmdletBinding()]
param(
    [string]$Workspace,
    [string]$PackageRoot,
    [ValidateRange(10,3600)]
    [int]$IntervalSeconds = 60,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Augmenter = Join-Path $PSScriptRoot 'augment_h2_final_package.py'
if ([string]::IsNullOrWhiteSpace($Workspace)) {
    $Workspace = Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
}
if ([string]::IsNullOrWhiteSpace($PackageRoot)) {
    $PackageRoot = Join-Path $ToolRoot 'JustPeachyResearchSummaries'
}
$Workspace = [IO.Path]::GetFullPath($Workspace)
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$WorkspaceCollectionPointerPath = Join-Path $Workspace 'final_augmented_collection.json'
$PackageCollectionPointerPath = Join-Path $PackageRoot 'LATEST_H2_AUGMENTED_PACKAGE.json'
foreach ($Path in @($Python, $Augmenter, $Workspace, $PackageRoot)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required H2 supplement path is unavailable: $Path"
    }
}
if ([IO.Path]::GetPathRoot($Workspace).TrimEnd('\').ToUpperInvariant() -ne 'C:') {
    throw 'The active H2 workspace must remain on drive C:.'
}
if ([IO.Path]::GetPathRoot($PackageRoot).TrimEnd('\').ToUpperInvariant() -ne 'C:') {
    throw 'The H2 package root must remain on drive C:.'
}

function Read-H2JsonSharedDelete {
    param([string]$Path)
    $Share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $Stream = [IO.File]::Open(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $Share
    )
    try {
        $Reader = [IO.StreamReader]::new(
            $Stream,
            [Text.Encoding]::UTF8,
            $true,
            4096,
            $true
        )
        try {
            return $Reader.ReadToEnd() | ConvertFrom-Json
        }
        finally {
            $Reader.Dispose()
        }
    }
    finally {
        $Stream.Dispose()
    }
}

function Get-H2FileSha256 {
    param([string]$LiteralPath)
    $Share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $Stream = [IO.File]::Open(
        $LiteralPath,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $Share
    )
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return -join @($Hasher.ComputeHash($Stream) | ForEach-Object {
            $_.ToString('x2')
        })
    }
    finally {
        $Hasher.Dispose()
        $Stream.Dispose()
    }
}

function Write-H2JsonAtomic {
    param(
        [string]$Path,
        [object]$Value
    )
    $Directory = [IO.Path]::GetDirectoryName($Path)
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    }
    $TemporaryPath = Join-Path $Directory (
        [IO.Path]::GetFileName($Path) + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    )
    $Utf8NoBom = New-Object Text.UTF8Encoding($false)
    $Json = ($Value | ConvertTo-Json -Depth 32) + [Environment]::NewLine
    [IO.File]::WriteAllText($TemporaryPath, $Json, $Utf8NoBom)
    try {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            [IO.File]::Replace($TemporaryPath, $Path, $null)
        }
        else {
            [IO.File]::Move($TemporaryPath, $Path)
        }
    }
    finally {
        if (Test-Path -LiteralPath $TemporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $TemporaryPath -Force
        }
    }
}

if ($DryRun) {
    [ordered]@{
        schema_version = 'h2-final-package-supplement-watcher-dry-run.v1'
        status = 'PASS'
        workspace = $Workspace
        package_root = $PackageRoot
        python = $Python
        augmenter = $Augmenter
        workspace_collection_pointer = $WorkspaceCollectionPointerPath
        package_collection_pointer = $PackageCollectionPointerPath
        required_enrollment_firewall_receipt = Join-Path $Workspace 'engineering_validation\enrollment_firewall_audit_receipt.json'
        current_program_status = if (Test-Path -LiteralPath (Join-Path $Workspace 'program_state.json')) {
            [string]((Read-H2JsonSharedDelete -Path (Join-Path $Workspace 'program_state.json')).status)
        } else {
            'NOT_YET_AVAILABLE'
        }
    } | ConvertTo-Json
    exit 0
}

$LogRoot = Join-Path $Workspace 'logs'
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
$LogPath = Join-Path $LogRoot 'final-package-supplement-watcher.jsonl'
$StatePath = Join-Path $Workspace 'program_state.json'
$StorageRoot = Join-Path $Workspace 'storage_maintenance'
$LifecyclePath = Join-Path $StorageRoot 'artifact_lifecycle.json'
$ForecastPath = Join-Path $StorageRoot 'storage_forecast.json'
$GuardianPassPath = Join-Path $StorageRoot 'last_guardian_pass.json'
$Arm64WheelReceiptPath = Join-Path $StorageRoot 'arm64_wheel_resolution_receipt.json'
$PruneReceiptRoot = Join-Path $StorageRoot 'receipts'
$UiLatencyReceiptPath = Join-Path $Workspace 'engineering_validation\ui_event_latency_receipt.json'
$EnrollmentFirewallReceiptPath = Join-Path $Workspace 'engineering_validation\enrollment_firewall_audit_receipt.json'

function Write-WatcherEvent {
    param([string]$Status, [string]$Detail)
    $Event = [ordered]@{
        schema_version = 'h2-final-package-supplement-watcher.v1'
        timestamp = [DateTimeOffset]::UtcNow.ToString('o')
        status = $Status
        detail = $Detail
    }
    ($Event | ConvertTo-Json -Compress) | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

Write-WatcherEvent -Status 'STARTED' -Detail "workspace=$Workspace; package_root=$PackageRoot"
while ($true) {
    try {
        if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
            Write-WatcherEvent -Status 'WAITING' -Detail 'program_state.json is not available yet'
            Start-Sleep -Seconds $IntervalSeconds
            continue
        }
        $State = Read-H2JsonSharedDelete -Path $StatePath
        $Status = [string]$State.status
        if ($Status -eq 'COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM') {
            $RequiredStorageSnapshots = @(
                $LifecyclePath,
                $ForecastPath,
                $GuardianPassPath,
                $Arm64WheelReceiptPath,
                $PruneReceiptRoot,
                $UiLatencyReceiptPath,
                $EnrollmentFirewallReceiptPath
            )
            if (@($RequiredStorageSnapshots | Where-Object {
                -not (Test-Path -LiteralPath $_)
            }).Count -gt 0) {
                Write-WatcherEvent -Status 'WAITING' -Detail (
                    'controller is complete but terminal storage snapshots, the signed UI ' +
                    'event-latency receipt, or the signed enrollment-firewall receipt are ' +
                    'not visible yet'
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
            $Lifecycle = Read-H2JsonSharedDelete -Path $LifecyclePath
            $Forecast = Read-H2JsonSharedDelete -Path $ForecastPath
            $GuardianPass = Read-H2JsonSharedDelete -Path $GuardianPassPath
            $PendingReceipts = @(
                Get-ChildItem -LiteralPath $PruneReceiptRoot `
                    -Filter '*.pending.json' -File -ErrorAction SilentlyContinue
            )
            $StateUpdated = [DateTimeOffset]::Parse([string]$State.updated_at_utc)
            $GuardianCompleted = [DateTimeOffset]::Parse(
                [string]$GuardianPass.completed_at_utc
            )
            $TerminalStorageReady = (
                [string]$Lifecycle.campaign_status -eq $Status -and
                [string]$Forecast.program_status -eq $Status -and
                [string]$GuardianPass.artifact_lifecycle_sha256 -eq `
                    [string]$Lifecycle.lifecycle_sha256 -and
                $GuardianCompleted -ge $StateUpdated -and
                $PendingReceipts.Count -eq 0
            )
            if (-not $TerminalStorageReady) {
                Write-WatcherEvent -Status 'WAITING' -Detail (
                    'controller is complete; waiting for the checksum-bound terminal ' +
                    'storage-guardian pass before final packaging'
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
            $FinalCollection = $State.final_collection
            $NativePath = if ($null -ne $FinalCollection) {
                [string]$FinalCollection.upload_path
            } else {
                ''
            }
            $ExpectedNativeSha256 = if ($null -ne $FinalCollection) {
                [string]$FinalCollection.zip_sha256
            } else {
                ''
            }
            if (
                [string]::IsNullOrWhiteSpace($NativePath) -or
                $ExpectedNativeSha256 -notmatch '^[0-9a-fA-F]{64}$'
            ) {
                Write-WatcherEvent -Status 'WAITING' -Detail (
                    'controller is complete but its exact final-collection ZIP binding ' +
                    'is not visible yet'
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
            $NativePath = [IO.Path]::GetFullPath($NativePath)
            $PackagePrefix = $PackageRoot.TrimEnd('\') + '\'
            if (-not $NativePath.StartsWith(
                $PackagePrefix,
                [StringComparison]::OrdinalIgnoreCase
            )) {
                throw "Terminal native ZIP escaped the configured package root: $NativePath"
            }
            if (
                -not (Test-Path -LiteralPath $NativePath -PathType Leaf) -or
                [IO.Path]::GetFileName($NativePath).EndsWith(
                    '_with_plots.zip',
                    [StringComparison]::OrdinalIgnoreCase
                )
            ) {
                Write-WatcherEvent -Status 'WAITING' -Detail (
                    "exact terminal native ZIP is not visible yet: $NativePath"
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
            $ObservedNativeSha256 = Get-H2FileSha256 -LiteralPath $NativePath
            if ($ObservedNativeSha256 -ne $ExpectedNativeSha256) {
                throw (
                    'Terminal native ZIP checksum differs from program_state.json: ' +
                    "expected=$ExpectedNativeSha256; observed=$ObservedNativeSha256"
                )
            }
            $Native = Get-Item -LiteralPath $NativePath
            Write-WatcherEvent -Status 'AUGMENTING' -Detail "source_zip=$($Native.FullName)"
            $Output = & $Python $Augmenter --source-zip $Native.FullName --workspace $Workspace --package-root $PackageRoot 2>&1
            $ExitCode = $LASTEXITCODE
            $Detail = ($Output -join "`n")
            if ($ExitCode -ne 0) {
                Write-WatcherEvent -Status 'FAILED' -Detail $Detail
                throw "H2 final-package augmentation failed with exit code $ExitCode"
            }
            $AugmentedPath = Join-Path $Native.DirectoryName (
                $Native.BaseName + '_with_plots.zip'
            )
            $AugmentedReceiptPath = $AugmentedPath + '.receipt.json'
            if (-not (Test-Path -LiteralPath $AugmentedReceiptPath -PathType Leaf)) {
                throw "Augmented package receipt is missing: $AugmentedReceiptPath"
            }
            $AugmentedReceipt = Read-H2JsonSharedDelete -Path $AugmentedReceiptPath
            $ReceiptSourcePath = [IO.Path]::GetFullPath(
                [string]$AugmentedReceipt.source_native_zip
            )
            $ReceiptUploadPath = [IO.Path]::GetFullPath(
                [string]$AugmentedReceipt.upload_path
            )
            if (
                [string]$AugmentedReceipt.schema_version -ne `
                    'h2-augmented-package-receipt.v1' -or
                [string]$AugmentedReceipt.status -ne 'VALID' -or
                $ReceiptSourcePath -ne $Native.FullName -or
                [string]$AugmentedReceipt.source_native_zip_sha256 -ne `
                    $ExpectedNativeSha256 -or
                $ReceiptUploadPath -ne [IO.Path]::GetFullPath($AugmentedPath) -or
                [string]$AugmentedReceipt.sha256 -notmatch '^[0-9a-fA-F]{64}$'
            ) {
                throw 'Augmented package receipt does not match the terminal native collection'
            }
            if (-not (Test-Path -LiteralPath $ReceiptUploadPath -PathType Leaf)) {
                throw "Augmented package is missing: $ReceiptUploadPath"
            }
            $ObservedAugmentedSha256 = Get-H2FileSha256 `
                -LiteralPath $ReceiptUploadPath
            if ($ObservedAugmentedSha256 -ne [string]$AugmentedReceipt.sha256) {
                throw (
                    'Augmented ZIP checksum differs from its receipt: ' +
                    "expected=$($AugmentedReceipt.sha256); " +
                    "observed=$ObservedAugmentedSha256"
                )
            }
            $CollectionPointer = [ordered]@{
                schema_version = 'h2-final-augmented-collection-pointer.v1'
                status = 'VALID'
                completed_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
                campaign_id = [string]$State.campaign_id
                protocol_id = [string]$State.protocol_id
                source_program_status = $Status
                source_program_state_updated_at_utc = [string]$State.updated_at_utc
                workspace = $Workspace
                package_root = $PackageRoot
                workspace_pointer_path = $WorkspaceCollectionPointerPath
                package_pointer_path = $PackageCollectionPointerPath
                publication_order = @(
                    'package_root_pointer',
                    'workspace_terminal_commit_pointer'
                )
                controller_program_state_preserved = $true
                scientific_content_unchanged = $true
                preferred_upload_artifact = 'augmented_collection'
                native_collection = [ordered]@{
                    upload_path = $Native.FullName
                    sha256 = $ExpectedNativeSha256
                }
                augmented_collection = [ordered]@{
                    upload_path = $ReceiptUploadPath
                    sha256 = [string]$AugmentedReceipt.sha256
                    receipt_path = [IO.Path]::GetFullPath($AugmentedReceiptPath)
                    validation = $AugmentedReceipt.validation
                }
            }
            Write-H2JsonAtomic `
                -Path $PackageCollectionPointerPath `
                -Value $CollectionPointer
            Write-H2JsonAtomic `
                -Path $WorkspaceCollectionPointerPath `
                -Value $CollectionPointer
            Write-WatcherEvent -Status 'COMPLETE' -Detail (
                $Detail + "`nworkspace_pointer=$WorkspaceCollectionPointerPath" +
                "`npackage_pointer=$PackageCollectionPointerPath"
            )
            [System.Media.SystemSounds]::Asterisk.Play()
            exit 0
        }
        if ($Status -in @('FAILED', 'BLOCKED_SCIENTIFIC_RUN', 'BLOCKED_OTHER')) {
            Write-WatcherEvent -Status 'CAMPAIGN_NOT_COMPLETE' -Detail "program_status=$Status"
            exit 2
        }
    }
    catch [System.Management.Automation.PipelineStoppedException] {
        throw
    }
    catch {
        Write-WatcherEvent -Status 'TRANSIENT_READ_OR_AUGMENT_ERROR' -Detail $_.Exception.Message
        if ((Get-Content -LiteralPath $LogPath -Tail 1) -match 'augmentation failed') {
            throw
        }
    }
    Start-Sleep -Seconds $IntervalSeconds
}
