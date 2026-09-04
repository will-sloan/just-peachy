[CmdletBinding()]
param(
    [string]$Workspace,
    [string]$ResultsRoot,
    [string]$SummaryRoot,
    [string]$Config,
    [ValidateRange(1,3600)]
    [int]$IntervalSeconds = 5,
    [switch]$Follow,
    [switch]$Once,
    [switch]$Json,
    [switch]$IncludeLiveCaseStatus,
    [switch]$NoMilestoneSound
)

$ErrorActionPreference = 'Stop'
if ($Follow -and $Once) { throw '-Follow and -Once cannot be used together.' }
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if ([string]::IsNullOrWhiteSpace($Workspace)) {
    $Workspace = Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
}
if ([string]::IsNullOrWhiteSpace($ResultsRoot)) {
    $ResultsRoot = Join-Path $ToolRoot 'JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17'
}
if ([string]::IsNullOrWhiteSpace($SummaryRoot)) {
    $SummaryRoot = Join-Path $ToolRoot 'JustPeachyResearchSummaries\h2_complete_product_pipeline_v17'
}
if ([string]::IsNullOrWhiteSpace($Config)) {
    $Config = Join-Path $ToolRoot 'configs\automated_evaluation\h2_product_program.v17.yaml'
}
$Workspace = [IO.Path]::GetFullPath($Workspace)
$ResultsRoot = [IO.Path]::GetFullPath($ResultsRoot)
$SummaryRoot = [IO.Path]::GetFullPath($SummaryRoot)
$Config = [IO.Path]::GetFullPath($Config)

$StatePath = Join-Path $Workspace 'program_state.json'
$ProgressPath = Join-Path $Workspace 'campaign_progress.json'
$ManifestPath = Join-Path $Workspace 'job_manifest.json'
$ProtocolManifestPath = Join-Path $Workspace 'protocol_manifest.json'
$MilestonesPath = Join-Path $Workspace 'milestones.jsonl'
$RunOwnerPath = Join-Path $Workspace 'h2_program_run.lock.owner.json'
$StorageForecastPath = Join-Path $Workspace 'storage_maintenance\storage_forecast.json'
$FinalPackagePointerPath = Join-Path $Workspace 'final_augmented_collection.json'
$FinalPackageWatcherLogPath = Join-Path $Workspace 'logs\final-package-supplement-watcher.jsonl'
$LegacyStatePath = Join-Path $ToolRoot 'runs\full_pipeline_program\PROGRAM_STATE.json'
$ShouldWatch = $Follow -or -not $Once
$script:H2PreviousHostPid = $null
$script:H2PreviousHostCpuSec = $null
$script:H2PreviousHostSampleUtc = $null
$script:H2PreviousWorkerRootPid = $null
$script:H2PreviousWorkerCpuSec = $null
$script:H2PreviousWorkerSampleUtc = $null
$script:H2PreviousWorkerFleetKey = $null
$script:H2PreviousWorkerFleetCpuSec = $null
$script:H2PreviousWorkerFleetSampleUtc = $null

function Read-H2SharedText {
    param([Parameter(Mandatory)][string]$LiteralPath)

    $Share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $Stream = [IO.File]::Open(
        $LiteralPath,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $Share
    )
    try {
        $Reader = New-Object IO.StreamReader($Stream, [Text.Encoding]::UTF8, $true)
        try { return $Reader.ReadToEnd() }
        finally { $Reader.Dispose() }
    }
    finally { $Stream.Dispose() }
}

function Read-H2SharedJson {
    param([Parameter(Mandatory)][string]$LiteralPath)

    return (Read-H2SharedText -LiteralPath $LiteralPath | ConvertFrom-Json)
}

function Get-H2FileSha256 {
    param([Parameter(Mandatory)][string]$LiteralPath)

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

function Get-H2Value {
    param($Value, $Default)

    if ($null -eq $Value) { return $Default }
    return $Value
}

function Get-H2PropertyValue {
    param($Object, [string]$Name, $Default)

    if ($null -eq $Object) { return $Default }
    $Property = $Object.PSObject.Properties[$Name]
    if ($null -eq $Property -or $null -eq $Property.Value) { return $Default }
    return $Property.Value
}

function Get-H2Bar {
    param([double]$Percent, [int]$Width = 24)

    $Bounded = [math]::Max(0.0, [math]::Min(100.0, $Percent))
    $Filled = [int][math]::Round($Width * $Bounded / 100.0)
    return '[' + ('#' * $Filled) + ('-' * ($Width - $Filled)) + ']'
}

function Format-H2Duration {
    param($Seconds)

    if ($null -eq $Seconds) { return 'calculating' }
    $Value = [double]$Seconds
    if ($Value -lt 0) { return 'calculating' }
    $Span = [TimeSpan]::FromSeconds($Value)
    if ($Span.TotalDays -ge 1) {
        return ('{0}d {1}h {2}m' -f [math]::Floor($Span.TotalDays), $Span.Hours, $Span.Minutes)
    }
    return ('{0}h {1}m {2}s' -f [math]::Floor($Span.TotalHours), $Span.Minutes, $Span.Seconds)
}

function Format-H2Value {
    param($Value, [string]$Suffix = '')

    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return 'measuring'
    }
    return ([string]$Value + $Suffix)
}

function ConvertTo-H2UtcDateTime {
    param($Value)

    if ($null -eq $Value) { return $null }
    if ($Value -is [DateTimeOffset]) { return $Value.UtcDateTime }
    if ($Value -is [DateTime]) {
        if ($Value.Kind -eq [DateTimeKind]::Unspecified) {
            return [DateTime]::SpecifyKind($Value, [DateTimeKind]::Utc)
        }
        return $Value.ToUniversalTime()
    }
    return [DateTimeOffset]::Parse(
        [string]$Value,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind
    ).UtcDateTime
}

function Get-H2FinalPackageStatus {
    $Status = [ordered]@{
        status = 'WAITING'
        watcher_status = 'NOT_STARTED'
        detail = 'waiting for terminal scientific completion'
        upload_path = $null
        sha256 = $null
        receipt_path = $null
        pointer_path = $FinalPackagePointerPath
    }
    if (Test-Path -LiteralPath $FinalPackageWatcherLogPath -PathType Leaf) {
        try {
            $Lines = @(
                (Read-H2SharedText -LiteralPath $FinalPackageWatcherLogPath) `
                    -split "`r?`n" |
                    Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
            )
            if ($Lines.Count -gt 0) {
                $WatcherEvent = $Lines[-1] | ConvertFrom-Json
                $Status.watcher_status = [string]$WatcherEvent.status
                $Status.detail = [string]$WatcherEvent.detail
            }
        }
        catch {
            $Status.watcher_status = 'TRANSIENT_READ_ERROR'
            $Status.detail = $_.Exception.Message
        }
    }
    if (-not (Test-Path -LiteralPath $FinalPackagePointerPath -PathType Leaf)) {
        if ($Status.watcher_status -eq 'FAILED') { $Status.status = 'FAILED' }
        return [pscustomobject]$Status
    }
    try {
        $Pointer = Read-H2SharedJson -LiteralPath $FinalPackagePointerPath
        $PackageRoot = [IO.Path]::GetDirectoryName($SummaryRoot.TrimEnd('\'))
        $UploadPath = [IO.Path]::GetFullPath(
            [string]$Pointer.augmented_collection.upload_path
        )
        $ReceiptPath = [IO.Path]::GetFullPath(
            [string]$Pointer.augmented_collection.receipt_path
        )
        $ExpectedSha256 = [string]$Pointer.augmented_collection.sha256
        $PackagePrefix = $PackageRoot.TrimEnd('\') + '\'
        $ExpectedPackagePointerPath = Join-Path `
            $PackageRoot 'LATEST_H2_AUGMENTED_PACKAGE.json'
        $PackagePointerPath = [IO.Path]::GetFullPath(
            [string]$Pointer.package_pointer_path
        )
        if (
            [string]$Pointer.schema_version -ne `
                'h2-final-augmented-collection-pointer.v1' -or
            [string]$Pointer.status -ne 'VALID' -or
            [string]$Pointer.source_program_status -ne `
                'COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM' -or
            [string]$Pointer.preferred_upload_artifact -ne `
                'augmented_collection' -or
            $Pointer.controller_program_state_preserved -ne $true -or
            $Pointer.scientific_content_unchanged -ne $true -or
            -not ([IO.Path]::GetFullPath([string]$Pointer.workspace)).Equals(
                $Workspace,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            -not ([IO.Path]::GetFullPath([string]$Pointer.package_root)).Equals(
                $PackageRoot,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            -not ([IO.Path]::GetFullPath(
                [string]$Pointer.workspace_pointer_path
            )).Equals(
                $FinalPackagePointerPath,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            -not $PackagePointerPath.Equals(
                $ExpectedPackagePointerPath,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            @($Pointer.publication_order).Count -ne 2 -or
            [string]$Pointer.publication_order[0] -ne 'package_root_pointer' -or
            [string]$Pointer.publication_order[1] -ne `
                'workspace_terminal_commit_pointer' -or
            -not $UploadPath.StartsWith(
                $PackagePrefix,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            $ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$' -or
            -not (Test-Path -LiteralPath $UploadPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $ReceiptPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $PackagePointerPath -PathType Leaf)
        ) {
            throw 'final augmented collection pointer failed structural validation'
        }
        $PackagePointer = Read-H2SharedJson -LiteralPath $PackagePointerPath
        if (
            [string]$PackagePointer.schema_version -ne `
                'h2-final-augmented-collection-pointer.v1' -or
            [string]$PackagePointer.status -ne 'VALID' -or
            -not ([IO.Path]::GetFullPath(
                [string]$PackagePointer.workspace_pointer_path
            )).Equals(
                $FinalPackagePointerPath,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            -not ([IO.Path]::GetFullPath(
                [string]$PackagePointer.augmented_collection.upload_path
            )).Equals(
                $UploadPath,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            [string]$PackagePointer.augmented_collection.sha256 -ne $ExpectedSha256
        ) {
            throw 'package-root pointer differs from the workspace commit pointer'
        }
        $ObservedSha256 = Get-H2FileSha256 -LiteralPath $UploadPath
        if ($ObservedSha256 -ne $ExpectedSha256) {
            throw (
                'final augmented ZIP checksum differs: ' +
                "expected=$ExpectedSha256; observed=$ObservedSha256"
            )
        }
        $Status.status = 'VALID'
        $Status.watcher_status = 'COMPLETE'
        $Status.detail = 'checksum-validated augmented upload artifact is ready'
        $Status.upload_path = $UploadPath
        $Status.sha256 = $ExpectedSha256
        $Status.receipt_path = $ReceiptPath
    }
    catch {
        $Status.status = 'INVALID'
        $Status.detail = $_.Exception.Message
    }
    return [pscustomobject]$Status
}

function Get-H2WorkClass {
    param($Job)

    $Kind = [string]$Job.job_kind
    if ($Kind -match 'bootstrap') { return 'bootstrap' }
    if ($Kind -match 'policy|replay|selection|freeze|analysis|collection|audit') {
        return 'policy'
    }
    if (@($Job.case_ids).Count -gt 0) { return 'neural' }
    return 'policy'
}

function Measure-H2WorkClass {
    param(
        [Parameter(Mandatory)]$ManifestJobs,
        [Parameter(Mandatory)]$StateJobs,
        [Parameter(Mandatory)]$ProgressById,
        [Parameter(Mandatory)][string]$WorkClass
    )

    $Total = 0.0
    $Complete = 0.0
    foreach ($Job in $ManifestJobs) {
        if ((Get-H2WorkClass -Job $Job) -ne $WorkClass) { continue }
        $StateProperty = $StateJobs.PSObject.Properties[[string]$Job.job_id]
        if ($null -eq $StateProperty) { continue }
        $StateRow = $StateProperty.Value
        if ([string]$StateRow.state -eq 'SUPERSEDED') { continue }
        $Units = [math]::Max(1, @($Job.case_ids).Count)
        $Total += $Units
        if ([string]$StateRow.state -eq 'COMPLETE') {
            $Complete += $Units
            continue
        }
        $ProgressRow = $ProgressById[[string]$Job.job_id]
        if ($null -ne $ProgressRow) {
            $ProgressCases = Get-H2PropertyValue -Object $ProgressRow -Name 'completed_cases' -Default 0
            $Complete += [math]::Min($Units, [double]$ProgressCases)
        }
    }
    if ($Total -le 0) { return $null }
    return [math]::Round(100.0 * $Complete / $Total, 2)
}

function Measure-H2DynamicCampaignProgress {
    param(
        [Parameter(Mandatory)]$ManifestJobs,
        [Parameter(Mandatory)]$StateJobs,
        [Parameter(Mandatory)]$ProgressById
    )

    $TotalUnits = 0.0
    $CompletedUnits = 0.0
    $ActiveJobs = 0
    $CompletedJobs = 0
    $PlannedCases = 0
    $CompletedCases = 0
    $PlannedAudioSec = 0.0
    $CompletedAudioSec = 0.0
    foreach ($Job in $ManifestJobs) {
        $StateProperty = $StateJobs.PSObject.Properties[[string]$Job.job_id]
        if ($null -eq $StateProperty) { continue }
        $StateRow = $StateProperty.Value
        if ([string]$StateRow.state -eq 'SUPERSEDED') { continue }

        $ActiveJobs += 1
        $CaseCount = @($Job.case_ids).Count
        $Units = [math]::Max(1, $CaseCount)
        $AudioSec = [double](
            Get-H2PropertyValue -Object $Job -Name 'audio_duration_sec' -Default 0.0
        )
        $TotalUnits += $Units
        $PlannedCases += $CaseCount
        $PlannedAudioSec += $AudioSec

        if ([string]$StateRow.state -eq 'COMPLETE') {
            $CompletedUnits += $Units
            $CompletedJobs += 1
            $CompletedCases += $CaseCount
            $CompletedAudioSec += $AudioSec
            continue
        }
        if ([string]$StateRow.state -ne 'RUNNING') { continue }

        $ProgressRow = $ProgressById[[string]$Job.job_id]
        $ProgressCases = if ($null -ne $ProgressRow) {
            Get-H2PropertyValue -Object $ProgressRow -Name 'completed_cases' -Default 0
        } else {
            Get-H2PropertyValue -Object $StateRow -Name 'completed_cases' -Default 0
        }
        $ProgressAudioSec = if ($null -ne $ProgressRow) {
            Get-H2PropertyValue -Object $ProgressRow -Name 'completed_audio_sec' -Default 0.0
        } else {
            Get-H2PropertyValue -Object $StateRow -Name 'completed_audio_sec' -Default 0.0
        }
        $BoundedCases = [math]::Min($CaseCount, [int]$ProgressCases)
        $CompletedUnits += [math]::Min($Units, [double]$ProgressCases)
        $CompletedCases += $BoundedCases
        $CompletedAudioSec += [math]::Min($AudioSec, [double]$ProgressAudioSec)
    }

    $Percent = if ($TotalUnits -gt 0) {
        [math]::Round(100.0 * $CompletedUnits / $TotalUnits, 2)
    } else { 0.0 }
    return [pscustomobject]@{
        overall_percentage = $Percent
        active_jobs = $ActiveJobs
        completed_jobs = $CompletedJobs
        planned_cases = $PlannedCases
        completed_cases = $CompletedCases
        planned_audio_sec = $PlannedAudioSec
        completed_audio_sec = $CompletedAudioSec
        total_units = $TotalUnits
        completed_units = $CompletedUnits
    }
}

function Get-H2BackendSummary {
    param([string]$PipelineId, $LegacyState)

    $Parts = @($PipelineId -split '_')
    if ($Parts.Count -lt 5 -or $null -eq $LegacyState) {
        return [pscustomobject]@{ ASR = $PipelineId; Diarization = '-'; Identity = '-' }
    }
    $Aliases = $LegacyState.component_aliases
    $AsrCode = [string]$Parts[-3]
    $DiarizationCode = [string]$Parts[-2]
    $IdentityCode = [string]$Parts[-1]
    return [pscustomobject]@{
        ASR = Get-H2PropertyValue -Object $Aliases.asr -Name $AsrCode.ToUpper() -Default $AsrCode
        Diarization = Get-H2PropertyValue -Object $Aliases.anonymous_diarization -Name $DiarizationCode.ToUpper() -Default $DiarizationCode
        Identity = Get-H2PropertyValue -Object $Aliases.identity -Name $IdentityCode.ToUpper() -Default $IdentityCode
    }
}

function Get-H2HostProcessSample {
    $Sample = [ordered]@{
        pid = $null
        cpu_percent = $null
        rss_mb = $null
        source = $null
    }
    if (-not (Test-Path -LiteralPath $RunOwnerPath -PathType Leaf)) {
        return $Sample
    }
    try {
        $Owner = Read-H2SharedJson -LiteralPath $RunOwnerPath
        $PidValue = [int](Get-H2PropertyValue -Object $Owner -Name 'pid' -Default 0)
        if ($PidValue -le 0) { return $Sample }
        $Process = Get-Process -Id $PidValue -ErrorAction Stop
        $Now = [datetime]::UtcNow
        $CpuSec = [double]$Process.TotalProcessorTime.TotalSeconds
        $CpuPercent = $null
        if (
            $script:H2PreviousHostPid -eq $PidValue -and
            $null -ne $script:H2PreviousHostCpuSec -and
            $null -ne $script:H2PreviousHostSampleUtc
        ) {
            $ElapsedSec = ($Now - $script:H2PreviousHostSampleUtc).TotalSeconds
            $CpuDeltaSec = $CpuSec - [double]$script:H2PreviousHostCpuSec
            if ($ElapsedSec -gt 0 -and $CpuDeltaSec -ge 0) {
                $CpuPercent = [math]::Round(
                    100.0 * $CpuDeltaSec /
                        ($ElapsedSec * [Environment]::ProcessorCount),
                    2
                )
            }
        }
        $script:H2PreviousHostPid = $PidValue
        $script:H2PreviousHostCpuSec = $CpuSec
        $script:H2PreviousHostSampleUtc = $Now
        $Sample.pid = $PidValue
        $Sample.cpu_percent = $CpuPercent
        $Sample.rss_mb = [math]::Round([double]$Process.WorkingSet64 / 1MB, 2)
        $Sample.source = 'controller_host_process_fallback'
    }
    catch {
        # A process hand-off between atomic jobs is expected and harmless.
        # The checksum-bound campaign progress snapshot remains primary.
    }
    return $Sample
}

function Get-H2ProcessTreeSample {
    param([int]$RootPid)

    $Sample = [ordered]@{
        root_pid = if ($RootPid -gt 0) { $RootPid } else { $null }
        process_ids = @()
        running = $false
        cpu_core_percent = $null
        rss_mb = $null
    }
    if ($RootPid -le 0) { return $Sample }
    try {
        $Rows = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        $Known = @{$RootPid = $true}
        do {
            $Added = $false
            foreach ($Row in $Rows) {
                $PidValue = [int]$Row.ProcessId
                $ParentPid = [int]$Row.ParentProcessId
                if (-not $Known.ContainsKey($PidValue) -and $Known.ContainsKey($ParentPid)) {
                    $Known[$PidValue] = $true
                    $Added = $true
                }
            }
        } while ($Added)

        $Processes = @(
            foreach ($PidValue in @($Known.Keys)) {
                Get-Process -Id ([int]$PidValue) -ErrorAction SilentlyContinue
            }
        )
        if ($Processes.Count -eq 0) { return $Sample }
        $Now = [datetime]::UtcNow
        $CpuSec = [double](
            ($Processes | Measure-Object -Property CPU -Sum).Sum
        )
        $CpuPercent = $null
        if (
            $script:H2PreviousWorkerRootPid -eq $RootPid -and
            $null -ne $script:H2PreviousWorkerCpuSec -and
            $null -ne $script:H2PreviousWorkerSampleUtc
        ) {
            $ElapsedSec = ($Now - $script:H2PreviousWorkerSampleUtc).TotalSeconds
            $CpuDeltaSec = $CpuSec - [double]$script:H2PreviousWorkerCpuSec
            if ($ElapsedSec -gt 0 -and $CpuDeltaSec -ge 0) {
                # One fully occupied logical core is 100%. Multiple worker threads
                # may legitimately exceed 100%, which is clearer than diluting the
                # value over every processor in the machine.
                $CpuPercent = [math]::Round(100.0 * $CpuDeltaSec / $ElapsedSec, 2)
            }
        }
        $script:H2PreviousWorkerRootPid = $RootPid
        $script:H2PreviousWorkerCpuSec = $CpuSec
        $script:H2PreviousWorkerSampleUtc = $Now
        $Sample.process_ids = @($Processes.Id | Sort-Object)
        $Sample.running = $true
        $Sample.cpu_core_percent = $CpuPercent
        $Sample.rss_mb = [math]::Round(
            [double](($Processes | Measure-Object -Property WorkingSet64 -Sum).Sum) / 1MB,
            2
        )
    }
    catch {
        # Worker hand-offs at case boundaries are expected. The status heartbeat
        # remains the primary activity signal during the hand-off.
    }
    return $Sample
}

function Get-H2WorkerFleetSample {
    param([int]$ControllerPid)

    $Sample = [ordered]@{
        root_pid = $null
        process_ids = @()
        running = $false
        cpu_core_percent = $null
        rss_mb = $null
        source = 'controller_descendant_worker_fallback'
    }
    if ($ControllerPid -le 0) { return $Sample }
    try {
        $Rows = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        $ControllerTree = @{$ControllerPid = $true}
        do {
            $Added = $false
            foreach ($Row in $Rows) {
                $PidValue = [int]$Row.ProcessId
                $ParentPid = [int]$Row.ParentProcessId
                if (
                    -not $ControllerTree.ContainsKey($PidValue) -and
                    $ControllerTree.ContainsKey($ParentPid)
                ) {
                    $ControllerTree[$PidValue] = $true
                    $Added = $true
                }
            }
        } while ($Added)

        $WorkerRoots = @(
            $Rows |
                Where-Object {
                    $ControllerTree.ContainsKey([int]$_.ProcessId) -and
                    [string]$_.CommandLine -match (
                        '(?:^|\s)-m\s+app\.full_pipeline\.worker_main(?:\s|$)'
                    )
                } |
                Sort-Object ProcessId
        )
        if ($WorkerRoots.Count -eq 0) { return $Sample }

        $WorkerIds = @{}
        foreach ($Row in $WorkerRoots) {
            $WorkerIds[[int]$Row.ProcessId] = $true
        }
        $RootIds = @(
            $WorkerRoots |
                Where-Object {
                    -not $WorkerIds.ContainsKey([int]$_.ParentProcessId)
                } |
                ForEach-Object { [int]$_.ProcessId } |
                Sort-Object
        )
        if ($RootIds.Count -eq 0) { return $Sample }
        do {
            $Added = $false
            foreach ($Row in $Rows) {
                $PidValue = [int]$Row.ProcessId
                $ParentPid = [int]$Row.ParentProcessId
                if (
                    -not $WorkerIds.ContainsKey($PidValue) -and
                    $WorkerIds.ContainsKey($ParentPid)
                ) {
                    $WorkerIds[$PidValue] = $true
                    $Added = $true
                }
            }
        } while ($Added)

        $Processes = @(
            foreach ($PidValue in @($WorkerIds.Keys)) {
                Get-Process -Id ([int]$PidValue) -ErrorAction SilentlyContinue
            }
        )
        if ($Processes.Count -eq 0) { return $Sample }

        $ProcessIds = @($Processes.Id | Sort-Object)
        $FleetKey = $ProcessIds -join ','
        $Now = [datetime]::UtcNow
        $CpuSec = [double](($Processes | Measure-Object -Property CPU -Sum).Sum)
        $CpuPercent = $null
        if (
            $script:H2PreviousWorkerFleetKey -eq $FleetKey -and
            $null -ne $script:H2PreviousWorkerFleetCpuSec -and
            $null -ne $script:H2PreviousWorkerFleetSampleUtc
        ) {
            $ElapsedSec = ($Now - $script:H2PreviousWorkerFleetSampleUtc).TotalSeconds
            $CpuDeltaSec = $CpuSec - [double]$script:H2PreviousWorkerFleetCpuSec
            if ($ElapsedSec -gt 0 -and $CpuDeltaSec -ge 0) {
                $CpuPercent = [math]::Round(100.0 * $CpuDeltaSec / $ElapsedSec, 2)
            }
        }
        $script:H2PreviousWorkerFleetKey = $FleetKey
        $script:H2PreviousWorkerFleetCpuSec = $CpuSec
        $script:H2PreviousWorkerFleetSampleUtc = $Now
        $Sample.root_pid = $RootIds[0]
        $Sample.process_ids = $ProcessIds
        $Sample.running = $true
        $Sample.cpu_core_percent = $CpuPercent
        $Sample.rss_mb = [math]::Round(
            [double](($Processes | Measure-Object -Property WorkingSet64 -Sum).Sum) / 1MB,
            2
        )
    }
    catch {
        # Process hand-offs are normal at atomic case boundaries. Durable
        # campaign counters remain authoritative if discovery races an exit.
    }
    return $Sample
}

function Get-H2CurrentCaseTelemetry {
    param(
        [Parameter(Mandatory)]$CurrentJob,
        [Parameter(Mandatory)]$CurrentProgress,
        [Parameter(Mandatory)]$Progress,
        [Parameter(Mandatory)]$ProtocolManifest
    )

    $Telemetry = [ordered]@{
        case_id = $null
        source_time_sec = $null
        duration_sec = $null
        percent = $null
        progress_bar = $null
        status_path = $null
        heartbeat_age_sec = $null
        activity = 'NOT_RUNNING'
        embedding_calls = $null
        embedding_rtf = $null
        queue_depth = $null
        queue_delay_ms = $null
        queue_backpressure_policy = $null
        queue_blocked_total_sec = $null
        queue_blocked_max_sec = $null
        dropped_frame_count = $null
        cache_hits = 0L
        cache_misses = 0L
        cache_hit_rate = $null
        worker_root_pid = $null
        worker_process_ids = @()
        worker_running = $false
        worker_cpu_core_percent = $null
        worker_rss_mb = $null
        worker_detection_source = $null
    }
    $CaseId = [string](
        Get-H2PropertyValue -Object $CurrentProgress -Name 'current_case_id' -Default (
            Get-H2PropertyValue -Object $Progress -Name 'current_case_id' -Default ''
        )
    )
    if ([string]::IsNullOrWhiteSpace($CaseId)) { return $Telemetry }
    $Telemetry.case_id = $CaseId

    $PreparedRoot = [string](
        Get-H2PropertyValue -Object $ProtocolManifest -Name 'prepared_protocol_root' -Default ''
    )
    $Split = [string](Get-H2PropertyValue -Object $CurrentJob -Name 'split' -Default '')
    if (-not [string]::IsNullOrWhiteSpace($PreparedRoot) -and -not [string]::IsNullOrWhiteSpace($Split)) {
        $CaseManifestPath = Join-Path $PreparedRoot (Join-Path $Split 'case_manifest.jsonl')
        if (Test-Path -LiteralPath $CaseManifestPath -PathType Leaf) {
            foreach ($Line in (Read-H2SharedText -LiteralPath $CaseManifestPath) -split "`r?`n") {
                if ([string]::IsNullOrWhiteSpace($Line) -or $Line -notmatch [regex]::Escape($CaseId)) {
                    continue
                }
                try {
                    $CaseRow = $Line | ConvertFrom-Json
                    if ([string]$CaseRow.protocol_case_id -eq $CaseId) {
                        $Telemetry.duration_sec = [double]$CaseRow.duration_sec
                        break
                    }
                }
                catch { }
            }
        }
    }

    # The runtime publishes this file repeatedly with an atomic replacement.
    # Some Windows filesystem/filter-driver combinations can transiently deny
    # that replacement even when a reader requests FileShare.Delete. Keep the
    # unattended/default monitor on durable campaign snapshots and make the
    # finer-grained hot-file view an explicit diagnostic opt-in.
    if (-not $IncludeLiveCaseStatus) {
        $Telemetry.activity = 'DURABLE_CASE_COUNTERS'
        $ControllerPid = 0
        if (Test-Path -LiteralPath $RunOwnerPath -PathType Leaf) {
            try {
                $Owner = Read-H2SharedJson -LiteralPath $RunOwnerPath
                $ControllerPid = [int](
                    Get-H2PropertyValue -Object $Owner -Name 'pid' -Default 0
                )
            }
            catch { }
        }
        $Worker = Get-H2WorkerFleetSample -ControllerPid $ControllerPid
        $Telemetry.worker_root_pid = $Worker.root_pid
        $Telemetry.worker_process_ids = @($Worker.process_ids)
        $Telemetry.worker_running = $Worker.running
        $Telemetry.worker_cpu_core_percent = $Worker.cpu_core_percent
        $Telemetry.worker_rss_mb = $Worker.rss_mb
        $Telemetry.worker_detection_source = $Worker.source
        return $Telemetry
    }

    $AttemptCount = [int](
        Get-H2PropertyValue -Object $CurrentProgress -Name 'attempt_count' -Default 1
    )
    $AttemptName = 'attempt_{0:D3}' -f ([math]::Max(1, $AttemptCount))
    $JobId = [string](Get-H2PropertyValue -Object $CurrentJob -Name 'job_id' -Default '')
    if ([string]::IsNullOrWhiteSpace($JobId)) { return $Telemetry }
    $StatusPath = Join-Path $Workspace (
        Join-Path 'attempts' (
            Join-Path $JobId (
                Join-Path $AttemptName (Join-Path 'runtime_cases' (Join-Path $CaseId 'status.json'))
            )
        )
    )
    $Telemetry.status_path = $StatusPath
    if (-not (Test-Path -LiteralPath $StatusPath -PathType Leaf)) {
        $Telemetry.activity = 'STARTING'
        return $Telemetry
    }

    try {
        $StatusItem = Get-Item -LiteralPath $StatusPath
        $Status = Read-H2SharedJson -LiteralPath $StatusPath
        $HeartbeatAgeSec = [math]::Max(
            0.0,
            ([datetime]::UtcNow - $StatusItem.LastWriteTimeUtc).TotalSeconds
        )
        $Telemetry.heartbeat_age_sec = [math]::Round($HeartbeatAgeSec, 1)
        $Telemetry.source_time_sec = [double](
            Get-H2PropertyValue -Object $Status -Name 'source_time_sec' -Default 0.0
        )
        $Telemetry.queue_depth = Get-H2PropertyValue `
            -Object $Status -Name 'queue_depth' -Default $null
        $Telemetry.dropped_frame_count = Get-H2PropertyValue `
            -Object $Status -Name 'dropped_frame_count' -Default $null
        $Backpressure = Get-H2PropertyValue `
            -Object $Status -Name 'queue_backpressure' -Default $null
        if ($null -ne $Backpressure) {
            $Telemetry.queue_backpressure_policy = Get-H2PropertyValue `
                -Object $Backpressure -Name 'policy' -Default $null
            $Telemetry.queue_blocked_total_sec = Get-H2PropertyValue `
                -Object $Backpressure -Name 'blocked_total_sec' -Default $null
            $Telemetry.queue_blocked_max_sec = Get-H2PropertyValue `
                -Object $Backpressure -Name 'blocked_max_sec' -Default $null
        }
        if ($null -ne $Telemetry.duration_sec -and [double]$Telemetry.duration_sec -gt 0) {
            $Percent = 100.0 * [double]$Telemetry.source_time_sec / [double]$Telemetry.duration_sec
            $Telemetry.percent = [math]::Round([math]::Min(100.0, $Percent), 2)
            $Telemetry.progress_bar = Get-H2Bar -Percent $Telemetry.percent
        }

        $SeenDetails = @{}
        $WorkerRootPid = 0
        foreach ($Component in @($Status.components)) {
            $DetailText = [string]$Component.reason.detail
            if ([string]::IsNullOrWhiteSpace($DetailText) -or $SeenDetails.ContainsKey($DetailText)) {
                continue
            }
            $SeenDetails[$DetailText] = $true
            try { $Detail = $DetailText | ConvertFrom-Json }
            catch { continue }
            $Embedding = Get-H2PropertyValue -Object $Detail -Name 'embedding_telemetry' -Default $null
            if ($null -ne $Embedding) {
                $Calls = [long](
                    Get-H2PropertyValue -Object $Embedding -Name 'embedding_requests' -Default 0
                )
                if ($null -eq $Telemetry.embedding_calls -or $Calls -gt $Telemetry.embedding_calls) {
                    $Telemetry.embedding_calls = $Calls
                    $Telemetry.embedding_rtf = Get-H2PropertyValue -Object $Embedding -Name 'embedding_rtf' -Default $null
                    $Telemetry.queue_delay_ms = Get-H2PropertyValue -Object $Embedding -Name 'queue_delay_ms' -Default $null
                }
            }
            $Shared = Get-H2PropertyValue -Object $Detail -Name 'shared_execution' -Default $null
            if ($null -ne $Shared) {
                $Telemetry.cache_hits += [long](
                    Get-H2PropertyValue -Object $Shared -Name 'cache_hits' -Default 0
                )
                $Telemetry.cache_misses += [long](
                    Get-H2PropertyValue -Object $Shared -Name 'cache_misses' -Default 0
                )
            }
            if (
                (Get-H2PropertyValue -Object $Detail -Name 'running' -Default $false) -eq $true -and
                [int](Get-H2PropertyValue -Object $Detail -Name 'pid' -Default 0) -gt 0
            ) {
                $WorkerRootPid = [int]$Detail.pid
            }
        }
        $CacheTotal = $Telemetry.cache_hits + $Telemetry.cache_misses
        if ($CacheTotal -gt 0) {
            $Telemetry.cache_hit_rate = [math]::Round(
                100.0 * $Telemetry.cache_hits / $CacheTotal,
                2
            )
        }
        $Worker = Get-H2ProcessTreeSample -RootPid $WorkerRootPid
        $Telemetry.worker_root_pid = $Worker.root_pid
        $Telemetry.worker_process_ids = @($Worker.process_ids)
        $Telemetry.worker_running = $Worker.running
        $Telemetry.worker_cpu_core_percent = $Worker.cpu_core_percent
        $Telemetry.worker_rss_mb = $Worker.rss_mb
        $Telemetry.worker_detection_source = 'live_case_status'

        $FreshThresholdSec = [math]::Max(180.0, 3.0 * [double]$IntervalSeconds)
        if ([string]$Status.state -ne 'running') {
            $Telemetry.activity = [string]$Status.state
        }
        elseif ($HeartbeatAgeSec -le $FreshThresholdSec -or [double]$Worker.cpu_core_percent -gt 0.5) {
            $Telemetry.activity = 'ACTIVE'
        }
        elseif ($Worker.running) {
            $Telemetry.activity = 'WORKER_ALIVE_CHECKING'
        }
        else {
            $Telemetry.activity = 'STALE_CHECK'
        }
    }
    catch {
        $Telemetry.activity = 'TRANSIENT_READ'
    }
    return $Telemetry
}

function Get-H2Snapshot {
    foreach ($Path in ($StatePath, $ProgressPath, $ManifestPath, $ProtocolManifestPath)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            throw "Required monitor input is unavailable: $Path"
        }
    }
    $State = Read-H2SharedJson -LiteralPath $StatePath
    $Progress = Read-H2SharedJson -LiteralPath $ProgressPath
    $Manifest = Read-H2SharedJson -LiteralPath $ManifestPath
    $ProtocolManifest = Read-H2SharedJson -LiteralPath $ProtocolManifestPath
    $LegacyState = if (Test-Path -LiteralPath $LegacyStatePath -PathType Leaf) {
        Read-H2SharedJson -LiteralPath $LegacyStatePath
    } else { $null }
    $LatestMilestone = $null
    if (Test-Path -LiteralPath $MilestonesPath -PathType Leaf) {
        $MilestoneLines = @(
            (Read-H2SharedText -LiteralPath $MilestonesPath) -split "`r?`n" |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        )
        if ($MilestoneLines.Count -gt 0) {
            $LatestMilestone = $MilestoneLines[-1] | ConvertFrom-Json
        }
    }

    $ProgressById = @{}
    foreach ($Row in @($Progress.jobs)) { $ProgressById[[string]$Row.job_id] = $Row }
    $CurrentJob = @($Manifest.jobs | Where-Object job_id -eq $State.current_job_id) |
        Select-Object -First 1
    if ($null -eq $CurrentJob) { $CurrentJob = [pscustomobject]@{} }
    $CurrentProgress = $ProgressById[[string]$State.current_job_id]
    if ($null -eq $CurrentProgress) { $CurrentProgress = [pscustomobject]@{} }
    $DynamicProgress = Measure-H2DynamicCampaignProgress `
        -ManifestJobs @($Manifest.jobs) -StateJobs $State.jobs `
        -ProgressById $ProgressById
    $PublishedOverall = Get-H2PropertyValue `
        -Object $Progress -Name 'overall_percentage' -Default $null
    $Overall = if ($null -ne $PublishedOverall) {
        [double]$PublishedOverall
    }
    else {
        [double]$DynamicProgress.overall_percentage
    }
    $ProgressBasis = if ($null -ne $PublishedOverall) {
        'campaign_progress_active_plan_units'
    }
    else {
        'predeclared_manifest_fallback_units'
    }
    $ActiveCompletedJobs = [int](
        Get-H2PropertyValue -Object $Progress -Name 'complete_jobs' `
            -Default $DynamicProgress.completed_jobs
    )
    $ActivePlannedJobs = [int](
        Get-H2PropertyValue -Object $Progress -Name 'planned_jobs' `
            -Default $DynamicProgress.active_jobs
    )
    $ActiveCompletedCases = [int](
        Get-H2PropertyValue -Object $Progress -Name 'completed_cases' `
            -Default $DynamicProgress.completed_cases
    )
    $ActivePlannedCases = [int](
        Get-H2PropertyValue -Object $Progress -Name 'planned_cases' `
            -Default $DynamicProgress.planned_cases
    )
    $ActiveCompletedAudioSec = [double](
        Get-H2PropertyValue -Object $Progress -Name 'completed_audio_sec' `
            -Default $DynamicProgress.completed_audio_sec
    )
    $ActivePlannedAudioSec = [double](
        Get-H2PropertyValue -Object $Progress -Name 'planned_audio_sec' `
            -Default $DynamicProgress.planned_audio_sec
    )
    $Started = ConvertTo-H2UtcDateTime -Value $State.started_at_utc
    $ElapsedSec = if ($null -ne $Started) {
        ([datetime]::UtcNow - $Started).TotalSeconds
    } else { $null }
    $EtaSec = $null
    if ($null -ne $ElapsedSec -and $ElapsedSec -ge 900 -and $Overall -ge 1.0) {
        $EtaSec = $ElapsedSec * (100.0 - $Overall) / $Overall
    }
    $Finish = if ($null -ne $EtaSec) {
        [datetime]::UtcNow.AddSeconds([double]$EtaSec).ToString('yyyy-MM-dd HH:mm:ssZ')
    } else { 'calculating' }
    $Backend = Get-H2BackendSummary -PipelineId ([string]$CurrentJob.pipeline_id) -LegacyState $LegacyState
    $Tuning = $CurrentJob.runtime_tuning
    $RedimInstances = if ([string]$Tuning.redim_execution_strategy -match 'R1_TWO') { 2 } else { 1 }
    $FreeGiB = [math]::Round((Get-PSDrive -Name C).Free / 1GB, 2)
    $StorageForecast = if (Test-Path -LiteralPath $StorageForecastPath -PathType Leaf) {
        Read-H2SharedJson -LiteralPath $StorageForecastPath
    } else { [pscustomobject]@{} }
    $StorageCapacity = Get-H2PropertyValue -Object $StorageForecast -Name 'capacity_protection' -Default ([pscustomobject]@{})
    $FinalPackage = Get-H2FinalPackageStatus
    $TargetHours = Get-H2PropertyValue -Object $State -Name 'target_wall_hours' -Default 192.0
    $CurrentPlanned = Get-H2PropertyValue -Object $CurrentProgress -Name 'planned_cases' -Default @($CurrentJob.case_ids).Count
    $CurrentCase = Get-H2CurrentCaseTelemetry -CurrentJob $CurrentJob -CurrentProgress $CurrentProgress -Progress $Progress -ProtocolManifest $ProtocolManifest
    $CurrentJobPercentage = [double](
        Get-H2PropertyValue -Object $CurrentProgress -Name 'percentage' -Default 0.0
    )
    $HostProcess = Get-H2HostProcessSample
    $ProgressCpu = Get-H2PropertyValue -Object $Progress -Name 'current_cpu_percent' -Default $null
    $ProgressRss = Get-H2PropertyValue -Object $Progress -Name 'current_rss_mb' -Default $null
    $CpuValue = if ($null -ne $ProgressCpu) { $ProgressCpu } else { $HostProcess.cpu_percent }
    $RssValue = if ($null -ne $ProgressRss) { $ProgressRss } else { $HostProcess.rss_mb }
    $CpuSource = if ($null -ne $ProgressCpu) { 'campaign_progress' } else { $HostProcess.source }
    $RssSource = if ($null -ne $ProgressRss) { 'campaign_progress' } else { $HostProcess.source }
    $QueueDepth = if ($null -ne $CurrentCase.queue_depth) {
        $CurrentCase.queue_depth
    } else {
        Get-H2PropertyValue -Object $Progress -Name 'current_queue_depth' -Default $null
    }
    $QueueDepthSource = if ($null -ne $CurrentCase.queue_depth) {
        'live_case_status'
    } else {
        'campaign_progress'
    }
    return [ordered]@{
        schema_version = 'h2-read-only-monitor.v7'
        status = [string]$State.status
        overall_percentage = [math]::Round($Overall, 2)
        progress_bar = Get-H2Bar -Percent $Overall
        target_wall_hours = [double]$TargetHours
        target_is_advisory_only = $State.target_is_advisory_only -ne $false
        automatic_cutoff = $false
        elapsed_sec = $ElapsedSec
        eta_sec = $EtaSec
        eta_basis = $ProgressBasis
        estimated_finish_utc = $Finish
        current_phase = [string]$State.current_phase_name
        current_configuration = [string]$CurrentJob.configuration_id
        current_job_id = [string]$State.current_job_id
        current_job_kind = [string]$CurrentJob.job_kind
        current_job_percentage = [math]::Round($CurrentJobPercentage, 2)
        current_job_progress_bar = Get-H2Bar -Percent $CurrentJobPercentage
        current_case_id = [string]$CurrentCase.case_id
        current_case_source_time_sec = $CurrentCase.source_time_sec
        current_case_duration_sec = $CurrentCase.duration_sec
        current_case_percentage = $CurrentCase.percent
        current_case_progress_bar = $CurrentCase.progress_bar
        current_case_heartbeat_age_sec = $CurrentCase.heartbeat_age_sec
        current_case_activity = $CurrentCase.activity
        current_mode = [string]$CurrentJob.mode
        pipeline_id = [string]$CurrentJob.pipeline_id
        asr_backend = [string]$Backend.ASR
        diarization_backend = [string]$Backend.Diarization
        identity_backend = [string]$Backend.Identity
        completed_jobs = $ActiveCompletedJobs
        planned_jobs = $ActivePlannedJobs
        completed_cases = $ActiveCompletedCases
        planned_cases = $ActivePlannedCases
        completed_audio_sec = $ActiveCompletedAudioSec
        planned_audio_sec = $ActivePlannedAudioSec
        predeclared_manifest_percentage = [math]::Round(
            [double]$DynamicProgress.overall_percentage,
            2
        )
        predeclared_manifest_jobs = [int]$DynamicProgress.active_jobs
        predeclared_manifest_cases = [int]$DynamicProgress.planned_cases
        predeclared_manifest_audio_sec = [double]$DynamicProgress.planned_audio_sec
        current_completed_cases = [int](Get-H2PropertyValue -Object $CurrentProgress -Name 'completed_cases' -Default 0)
        current_planned_cases = [int]$CurrentPlanned
        neural_inference_percentage = Measure-H2WorkClass -ManifestJobs @($Manifest.jobs) -StateJobs $State.jobs -ProgressById $ProgressById -WorkClass 'neural'
        policy_replay_percentage = Measure-H2WorkClass -ManifestJobs @($Manifest.jobs) -StateJobs $State.jobs -ProgressById $ProgressById -WorkClass 'policy'
        bootstrap_percentage = Measure-H2WorkClass -ManifestJobs @($Manifest.jobs) -StateJobs $State.jobs -ProgressById $ProgressById -WorkClass 'bootstrap'
        configured_model_instances = "Pyannote=1; ReDimNet=$RedimInstances; Sherpa=1"
        embedding_calls = $CurrentCase.embedding_calls
        embedding_rtf = $CurrentCase.embedding_rtf
        cache_hits = [long]$CurrentCase.cache_hits
        cache_misses = [long]$CurrentCase.cache_misses
        cache_hit_rate = $CurrentCase.cache_hit_rate
        rolling_rtf = $Progress.rolling_rtf
        cpu_percent = $CpuValue
        cpu_percent_source = $CpuSource
        rss_mb = $RssValue
        rss_mb_source = $RssSource
        sampled_host_process_id = $HostProcess.pid
        queue_depth = $QueueDepth
        queue_depth_source = $QueueDepthSource
        queue_delay_ms = $CurrentCase.queue_delay_ms
        queue_backpressure_policy = $CurrentCase.queue_backpressure_policy
        queue_blocked_total_sec = $CurrentCase.queue_blocked_total_sec
        queue_blocked_max_sec = $CurrentCase.queue_blocked_max_sec
        dropped_frame_count = $CurrentCase.dropped_frame_count
        worker_root_pid = $CurrentCase.worker_root_pid
        worker_process_ids = @($CurrentCase.worker_process_ids)
        worker_running = $CurrentCase.worker_running
        worker_cpu_core_percent = $CurrentCase.worker_cpu_core_percent
        worker_rss_mb = $CurrentCase.worker_rss_mb
        worker_detection_source = $CurrentCase.worker_detection_source
        failed_jobs = [int](Get-H2PropertyValue -Object $Progress -Name 'failed_jobs' -Default 0)
        recovered_failed_attempts = [int](Get-H2PropertyValue -Object $Progress -Name 'failures' -Default 0)
        retries = [int](Get-H2PropertyValue -Object $Progress -Name 'retries' -Default 0)
        latest_activity = $Progress.latest_activity
        latest_milestone_id = Get-H2PropertyValue -Object $LatestMilestone -Name 'milestone_id' -Default $null
        latest_milestone_detail = Get-H2PropertyValue -Object $LatestMilestone -Name 'detail' -Default $null
        latest_milestone_recorded_at_utc = Get-H2PropertyValue -Object $LatestMilestone -Name 'recorded_at_utc' -Default $null
        free_gib = $FreeGiB
        reserve_satisfied = $FreeGiB -ge 35.0
        storage_risk = Get-H2PropertyValue -Object $StorageCapacity -Name 'risk' -Default 'measuring'
        storage_estimated_peak_gib = Get-H2PropertyValue -Object $StorageForecast -Name 'estimated_peak_next_single_job_gib' -Default $null
        storage_projected_free_gib = Get-H2PropertyValue -Object $StorageCapacity -Name 'projected_free_after_largest_job_gib' -Default $null
        storage_guardian_updated_at_utc = Get-H2PropertyValue -Object $StorageForecast -Name 'updated_at_utc' -Default $null
        final_package_status = $FinalPackage.status
        final_package_watcher_status = $FinalPackage.watcher_status
        final_package_detail = $FinalPackage.detail
        final_package_upload_path = $FinalPackage.upload_path
        final_package_sha256 = $FinalPackage.sha256
        final_package_receipt_path = $FinalPackage.receipt_path
        final_package_pointer_path = $FinalPackage.pointer_path
        updated_at_utc = $Progress.updated_at_utc
        workspace = $Workspace
        results_root = $ResultsRoot
        summary_root = $SummaryRoot
        config = $Config
        monitor_writes_scientific_state = $false
    }
}

function Show-H2Snapshot {
    param([Parameter(Mandatory)]$Snapshot)

    if ($ShouldWatch) { Clear-Host }
    Write-Host 'H2 PRODUCT PROGRAM' -ForegroundColor Cyan
    Write-Host ''
    Write-Host ('Overall:              {0} {1,6:N2}%' -f $Snapshot.progress_bar, $Snapshot.overall_percentage)
    Write-Host ('Progress basis:       {0}' -f $Snapshot.eta_basis) -ForegroundColor DarkGray
    Write-Host ('Target compute:       {0:N0} hours / {1:N1} days (advisory; no cutoff)' -f $Snapshot.target_wall_hours, ($Snapshot.target_wall_hours / 24.0))
    Write-Host ('Elapsed:              {0}' -f (Format-H2Duration $Snapshot.elapsed_sec))
    Write-Host ('Current ETA:          {0}' -f (Format-H2Duration $Snapshot.eta_sec))
    Write-Host ('Estimated finish:     {0}' -f $Snapshot.estimated_finish_utc)
    Write-Host ''
    Write-Host ('Current phase:        {0}' -f $Snapshot.current_phase)
    Write-Host ('Current configuration:{0}' -f (' ' + $Snapshot.current_configuration))
    Write-Host ('Current job work:     {0} {1,6:N2}%' -f $Snapshot.current_job_progress_bar, $Snapshot.current_job_percentage)
    Write-Host ('Current job:          {0}' -f $Snapshot.current_job_id)
    Write-Host ('Current mode:         {0}' -f $Snapshot.current_mode)
    Write-Host ('Current case:         {0}' -f $Snapshot.current_case_id)
    if ($null -ne $Snapshot.current_case_percentage) {
        Write-Host ('Current case work:    {0} {1,6:N2}% ({2:N1} / {3:N1} source sec)' -f $Snapshot.current_case_progress_bar, $Snapshot.current_case_percentage, $Snapshot.current_case_source_time_sec, $Snapshot.current_case_duration_sec)
    }
    Write-Host ('Case heartbeat:       {0}; age={1}' -f (Format-H2Value $Snapshot.current_case_activity), (Format-H2Value -Value $Snapshot.current_case_heartbeat_age_sec -Suffix ' sec'))
    Write-Host ('Jobs:                 {0} / {1} active plan' -f $Snapshot.completed_jobs, $Snapshot.planned_jobs)
    Write-Host ('Predeclared ceiling:  {0}% across {1} jobs; unpromoted candidates are not active work' -f $Snapshot.predeclared_manifest_percentage, $Snapshot.predeclared_manifest_jobs) -ForegroundColor DarkGray
    Write-Host ('Cases:                {0} / {1} overall; {2} / {3} current job' -f $Snapshot.completed_cases, $Snapshot.planned_cases, $Snapshot.current_completed_cases, $Snapshot.current_planned_cases)
    Write-Host 'Case counter cadence: advances after a checksum-valid case shard seals' -ForegroundColor DarkGray
    Write-Host ('Audio:                {0:N2} / {1:N2} hours' -f ($Snapshot.completed_audio_sec / 3600.0), ($Snapshot.planned_audio_sec / 3600.0))
    Write-Host ('Neural inference:     {0}' -f (Format-H2Value -Value $Snapshot.neural_inference_percentage -Suffix '%'))
    Write-Host ('Policy replay:        {0}' -f (Format-H2Value -Value $Snapshot.policy_replay_percentage -Suffix '%'))
    Write-Host ('Bootstrap:            {0}' -f (Format-H2Value -Value $Snapshot.bootstrap_percentage -Suffix '%'))
    Write-Host ''
    Write-Host ('ASR backend:          {0}' -f $Snapshot.asr_backend)
    Write-Host ('Diarization backend:  {0}' -f $Snapshot.diarization_backend)
    Write-Host ('Identity backend:     {0}' -f $Snapshot.identity_backend)
    Write-Host ('Configured models:    {0}' -f $Snapshot.configured_model_instances)
    Write-Host ('Embedding calls/RTF:  {0} / {1}' -f (Format-H2Value $Snapshot.embedding_calls), (Format-H2Value $Snapshot.embedding_rtf))
    Write-Host ('Cache:                rate={0}; hits={1}; misses={2}' -f (Format-H2Value -Value $Snapshot.cache_hit_rate -Suffix '%'), $Snapshot.cache_hits, $Snapshot.cache_misses)
    Write-Host ('RTF:                  {0}' -f (Format-H2Value $Snapshot.rolling_rtf))
    Write-Host ('CPU:                  {0} ({1})' -f (Format-H2Value -Value $Snapshot.cpu_percent -Suffix '%'), (Format-H2Value $Snapshot.cpu_percent_source))
    Write-Host ('RAM:                  {0} ({1})' -f (Format-H2Value -Value $Snapshot.rss_mb -Suffix ' MB'), (Format-H2Value $Snapshot.rss_mb_source))
    if (
        -not $Snapshot.worker_running -and
        $Snapshot.status -eq 'RUNNING' -and
        -not [string]::IsNullOrWhiteSpace([string]$Snapshot.current_case_id)
    ) {
        Write-Host ((
            'Separate worker fleet: none observed; current case is active via {0}. ' +
            'This does not mean the controller is stuck.'
        ) -f (Format-H2Value $Snapshot.current_case_activity)) -ForegroundColor DarkGray
    }
    else {
        Write-Host ('Separate worker fleet: running={0}; CPU={1}; RAM={2}; PIDs={3}; source={4}' -f $Snapshot.worker_running, (Format-H2Value -Value $Snapshot.worker_cpu_core_percent -Suffix '% of one core'), (Format-H2Value -Value $Snapshot.worker_rss_mb -Suffix ' MB'), ((@($Snapshot.worker_process_ids) -join ',') | ForEach-Object { if ([string]::IsNullOrWhiteSpace($_)) { 'measuring' } else { $_ } }), (Format-H2Value $Snapshot.worker_detection_source))
    }
    Write-Host ('Queue depth/delay:    {0} / {1} ({2})' -f (Format-H2Value $Snapshot.queue_depth), (Format-H2Value -Value $Snapshot.queue_delay_ms -Suffix ' ms'), (Format-H2Value $Snapshot.queue_depth_source))
    if ($null -ne $Snapshot.queue_backpressure_policy) {
        Write-Host ('Queue backpressure:   {0}; blocked total={1}; max={2}; dropped={3}' -f (Format-H2Value $Snapshot.queue_backpressure_policy), (Format-H2Value -Value $Snapshot.queue_blocked_total_sec -Suffix ' sec'), (Format-H2Value -Value $Snapshot.queue_blocked_max_sec -Suffix ' sec'), (Format-H2Value $Snapshot.dropped_frame_count))
    }
    Write-Host ('Failed jobs:          {0}' -f $Snapshot.failed_jobs)
    Write-Host ('Recovered / retries:  {0} / {1}' -f $Snapshot.recovered_failed_attempts, $Snapshot.retries)
    Write-Host ('C: free/reserve:      {0:N2} GiB / {1}' -f $Snapshot.free_gib, $Snapshot.reserve_satisfied)
    Write-Host ('Storage projection:   risk={0}; peak={1}; free after={2}' -f (Format-H2Value $Snapshot.storage_risk), (Format-H2Value -Value $Snapshot.storage_estimated_peak_gib -Suffix ' GiB'), (Format-H2Value -Value $Snapshot.storage_projected_free_gib -Suffix ' GiB'))
    Write-Host ('Storage guardian:     {0}' -f (Format-H2Value $Snapshot.storage_guardian_updated_at_utc))
    Write-Host ('Final package:        {0}; watcher={1}' -f (Format-H2Value $Snapshot.final_package_status), (Format-H2Value $Snapshot.final_package_watcher_status))
    Write-Host ('Latest activity:      {0}' -f $Snapshot.latest_activity)
    Write-Host ('Latest milestone:     {0}' -f (Format-H2Value $Snapshot.latest_milestone_detail))
    Write-Host ('Updated:              {0}' -f $Snapshot.updated_at_utc)
    Write-Host ''
    if ([string]$Snapshot.status -like 'COMPLETE*') {
        if ([string]$Snapshot.final_package_status -eq 'VALID') {
            Write-Host 'UPLOAD THIS FILE TO CHATGPT:' -ForegroundColor Green
            Write-Host ([string]$Snapshot.final_package_upload_path) -ForegroundColor Green
            Write-Host 'SHA-256:' -ForegroundColor Green
            Write-Host ([string]$Snapshot.final_package_sha256) -ForegroundColor Green
            Write-Host ''
        }
        else {
            Write-Host (
                'Scientific controller complete; waiting for the validated augmented ' +
                'package pointer.'
            ) -ForegroundColor Yellow
            Write-Host ('Package detail: {0}' -f $Snapshot.final_package_detail) -ForegroundColor Yellow
            Write-Host ''
        }
    }
    if ($IncludeLiveCaseStatus) {
        Write-Host 'Live-case status polling is enabled for diagnostics.' -ForegroundColor Yellow
    }
    else {
        Write-Host 'Uses durable snapshots only; hot live-case files are not opened.' -ForegroundColor DarkGray
    }
    Write-Host 'This monitor never writes scientific state.' -ForegroundColor DarkGray
    Write-Host 'Ctrl+C closes only the monitor.' -ForegroundColor DarkGray
}

$PreviousMilestoneId = $null
$FirstSnapshot = $true
while ($true) {
    try {
        $Snapshot = Get-H2Snapshot
        if (
            $ShouldWatch -and
            -not $FirstSnapshot -and
            -not $NoMilestoneSound -and
            -not [string]::IsNullOrWhiteSpace([string]$Snapshot.latest_milestone_id) -and
            [string]$Snapshot.latest_milestone_id -ne [string]$PreviousMilestoneId
        ) {
            try { [System.Media.SystemSounds]::Exclamation.Play() }
            catch { try { [console]::Beep(880, 450) } catch { } }
        }
        $PreviousMilestoneId = $Snapshot.latest_milestone_id
        $FirstSnapshot = $false
        if ($Json) { $Snapshot | ConvertTo-Json -Depth 8 -Compress }
        else { Show-H2Snapshot -Snapshot $Snapshot }
        $TerminalPackageReady = (
            [string]$Snapshot.status -like 'COMPLETE*' -and
            [string]$Snapshot.final_package_status -eq 'VALID'
        )
        if (-not $ShouldWatch -or $TerminalPackageReady -or [string]$Snapshot.status -eq 'STOPPED') {
            exit 0
        }
    }
    catch {
        if (-not $ShouldWatch) { throw }
        Write-Host ('Transient shared-read error: {0}' -f $_.Exception.Message) -ForegroundColor Yellow
    }
    Start-Sleep -Seconds $IntervalSeconds
}
