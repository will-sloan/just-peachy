[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $Workspace,

    [Parameter(Mandatory = $true)]
    [string] $ResultsRoot,

    [string[]] $CandidateJobIds,

    [ValidateSet("Phase1AccuracyPromotion", "SerialResource")]
    [string] $EvidenceClass = "Phase1AccuracyPromotion",

    [switch] $AllowNonidenticalReferences,

    [string] $OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-SharedJson {
    param([Parameter(Mandatory = $true)][string] $LiteralPath)

    $sharing = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $stream = [IO.FileStream]::new(
        $LiteralPath,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $sharing
    )
    try {
        $reader = [IO.StreamReader]::new($stream)
        try {
            $text = $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
    return $text | ConvertFrom-Json
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string] $LiteralPath)

    $sharing = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $stream = [IO.FileStream]::new(
        $LiteralPath,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $sharing
    )
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $hash = $algorithm.ComputeHash($stream)
        return (($hash | ForEach-Object { $_.ToString("x2") }) -join "")
    }
    finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}

function ConvertTo-UtcIso {
    param([Parameter(Mandatory = $true)][datetime] $Value)

    return $Value.ToUniversalTime().ToString("o")
}

function ConvertFrom-UtcJsonTimestamp {
    param([Parameter(Mandatory = $true)] $Value)

    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset] $Value).ToUniversalTime()
    }
    if ($Value -is [datetime]) {
        $dateTime = [datetime] $Value
        if ($dateTime.Kind -eq [DateTimeKind]::Utc) {
            return [DateTimeOffset]::new($dateTime)
        }
        if ($dateTime.Kind -eq [DateTimeKind]::Local) {
            # PowerShell 7 ConvertFrom-Json materializes an ISO-8601 value with
            # an explicit local offset as a Local DateTime. Preserve that
            # instant; relabelling the clock fields as UTC shifts the evidence
            # window by the host offset and assigns OS events to the wrong job.
            return [DateTimeOffset]::new($dateTime).ToUniversalTime()
        }
        # Legacy controller records without a suffix are defined by their
        # *_utc field contract. Treat only genuinely Unspecified values as UTC.
        $utcDateTime = [datetime]::SpecifyKind($dateTime, [DateTimeKind]::Utc)
        return [DateTimeOffset]::new($utcDateTime)
    }
    $parsed = [DateTimeOffset]::Parse(
        [string] $Value,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind
    )
    return $parsed.ToUniversalTime()
}

function Test-WithinCandidateInterval {
    param(
        [Parameter(Mandatory = $true)] $Value,
        [Parameter(Mandatory = $true)][object[]] $CandidateRows
    )

    $instant = ConvertFrom-UtcJsonTimestamp $Value
    foreach ($candidate in $CandidateRows) {
        $started = ConvertFrom-UtcJsonTimestamp $candidate.started_at_utc
        $completed = ConvertFrom-UtcJsonTimestamp $candidate.completed_at_utc
        if ($instant -ge $started -and $instant -le $completed) {
            return $true
        }
    }
    return $false
}

function Protect-HostText {
    param([AllowNull()][string] $Value)

    if ($null -eq $Value) {
        return $null
    }
    $protected = $Value
    foreach ($replacement in @(
        @($WorkspacePath, "%WORKSPACE%"),
        @($ResultsRootPath, "%RESULTS_ROOT%"),
        @($env:USERPROFILE, "%USERPROFILE%"),
        @($env:WINDIR, "%WINDIR%")
    )) {
        $source = [string] $replacement[0]
        if (-not [string]::IsNullOrWhiteSpace($source)) {
            $protected = [regex]::Replace(
                $protected,
                [regex]::Escape($source),
                [string] $replacement[1],
                [Text.RegularExpressions.RegexOptions]::IgnoreCase
            )
        }
    }
    return ($protected -replace "\s+", " ").Trim()
}

function Get-ReportedIoSeconds {
    param([AllowNull()][string] $Message)

    if ($null -eq $Message) {
        return $null
    }
    if ($Message -match "took an abnormally long time \((\d+) seconds\)") {
        return [int] $Matches[1]
    }
    if ($Message -match "has not completed for (\d+) second") {
        return [int] $Matches[1]
    }
    return $null
}

function Convert-EventRecord {
    param([Parameter(Mandatory = $true)] $Event)

    return [ordered]@{
        time_created_utc = ConvertTo-UtcIso $Event.TimeCreated
        provider = [string] $Event.ProviderName
        event_id = [int] $Event.Id
        level = [string] $Event.LevelDisplayName
        reported_io_seconds = Get-ReportedIoSeconds $Event.Message
        message = Protect-HostText $Event.Message
    }
}

function Test-ResultChecksums {
    param([Parameter(Mandatory = $true)][string] $ResultPath)

    $checksumPath = Join-Path $ResultPath "checksums.json"
    $checksumDocument = Get-Content -LiteralPath $checksumPath -Raw | ConvertFrom-Json
    $entries = @($checksumDocument.entries.PSObject.Properties)
    $failures = [System.Collections.Generic.List[object]]::new()
    foreach ($entry in $entries) {
        $relative = [string] $entry.Name
        $candidate = Join-Path $ResultPath ($relative -replace "/", "\")
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $failures.Add([ordered]@{ path = $relative; reason = "missing" })
            continue
        }
        $item = Get-Item -LiteralPath $candidate
        if ([int64] $item.Length -ne [int64] $entry.Value.bytes) {
            $failures.Add(
                [ordered]@{
                    path = $relative
                    reason = "size_mismatch"
                    expected_bytes = [int64] $entry.Value.bytes
                    actual_bytes = [int64] $item.Length
                }
            )
            continue
        }
        $actual = Get-Sha256 $candidate
        if ($actual -ne [string] $entry.Value.sha256) {
            $failures.Add(
                [ordered]@{
                    path = $relative
                    reason = "sha256_mismatch"
                    expected_sha256 = [string] $entry.Value.sha256
                    actual_sha256 = $actual
                }
            )
        }
    }
    return [ordered]@{
        status = if ($failures.Count -eq 0) { "VALID" } else { "INVALID" }
        declared_entry_count = $entries.Count
        verified_entry_count = $entries.Count - $failures.Count
        failures = @($failures)
        checksums_sha256 = Get-Sha256 $checksumPath
        reference_hashes = [ordered]@{
            cases = [string] $checksumDocument.entries."references/cases.jsonl".sha256
            enrollment_registry = [string] $checksumDocument.entries."references/selected_enrollment_registry.jsonl".sha256
            identity_overlays = [string] $checksumDocument.entries."references/selected_identity_overlays.jsonl".sha256
            speaker_attributed_transcripts = [string] $checksumDocument.entries."references/selected_speaker_attributed_transcripts.jsonl".sha256
        }
    }
}

function Read-CaseStatusRows {
    param([Parameter(Mandatory = $true)][string] $LiteralPath)

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($line in Get-Content -LiteralPath $LiteralPath) {
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            $rows.Add(($line | ConvertFrom-Json))
        }
    }
    return @($rows)
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string] $LiteralPath,
        [Parameter(Mandatory = $true)] $Value
    )

    $parent = Split-Path -Parent $LiteralPath
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = Join-Path $parent (".{0}.{1}.tmp" -f (Split-Path -Leaf $LiteralPath), [guid]::NewGuid().ToString("N"))
    $backup = Join-Path $parent (".{0}.{1}.bak" -f (Split-Path -Leaf $LiteralPath), [guid]::NewGuid().ToString("N"))
    try {
        $json = $Value | ConvertTo-Json -Depth 14
        [IO.File]::WriteAllText(
            $temporary,
            $json + [Environment]::NewLine,
            [Text.UTF8Encoding]::new($false)
        )
        if (Test-Path -LiteralPath $LiteralPath -PathType Leaf) {
            [IO.File]::Replace($temporary, $LiteralPath, $backup, $true)
            [IO.File]::Delete($backup)
        }
        else {
            [IO.File]::Move($temporary, $LiteralPath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
        if (Test-Path -LiteralPath $backup) {
            Remove-Item -LiteralPath $backup -Force
        }
    }
}

$WorkspacePath = [IO.Path]::GetFullPath($Workspace)
$ResultsRootPath = [IO.Path]::GetFullPath($ResultsRoot)
if (-not (Test-Path -LiteralPath $WorkspacePath -PathType Container)) {
    throw "Workspace does not exist: $WorkspacePath"
}
if (-not (Test-Path -LiteralPath $ResultsRootPath -PathType Container)) {
    throw "Results root does not exist: $ResultsRootPath"
}
if (-not $WorkspacePath.StartsWith("C:\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "H2 workspace is not on C:"
}
if (-not $ResultsRootPath.StartsWith("C:\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "H2 results root is not on C:"
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $outputName = if ($EvidenceClass -eq "SerialResource") {
        "serial_resource_host_io_eligibility.json"
    }
    else {
        "windows_host_io_interference.json"
    }
    $OutputPath = Join-Path $WorkspacePath "diagnostics\host_io_interference\$outputName"
}
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if (-not $OutputPath.StartsWith(
    $WorkspacePath.TrimEnd("\") + "\",
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Output must remain inside the H2 workspace"
}

$statePath = Join-Path $WorkspacePath "program_state.json"
$manifestPath = Join-Path $WorkspacePath "job_manifest.json"
$promotionPath = Join-Path $WorkspacePath "promotions\phase_1_full.json"
$guardianPath = Join-Path $WorkspacePath "logs\storage_guardian.supervised.stdout.log"
$state = Read-SharedJson $statePath
$manifest = Read-SharedJson $manifestPath
if ([string] $state.protocol_id -ne [string] $manifest.protocol_id) {
    throw "Program state and job manifest protocol IDs differ"
}
if ([string] $state.job_manifest_sha256 -ne [string] $manifest.job_manifest_sha256) {
    throw "Program state and job manifest hashes differ"
}
$jobManifestFileSha256 = Get-Sha256 $manifestPath
$manifestJobs = @($manifest.jobs)
$manifestById = @{}
foreach ($manifestJob in $manifestJobs) {
    $manifestById[[string] $manifestJob.job_id] = $manifestJob
}
if (-not $PSBoundParameters.ContainsKey("CandidateJobIds") -or @($CandidateJobIds).Count -eq 0) {
    if ($EvidenceClass -eq "SerialResource") {
        $CandidateJobIds = @(
            $manifestJobs |
                Where-Object {
                    [bool] $_.serial -and
                    [string] $_.job_kind -in @(
                        "resource_runtime",
                        "post_selection_resource_runtime"
                    )
                } |
                Select-Object -ExpandProperty job_id
        )
    }
    else {
        $CandidateJobIds = @(
            "h2p1_s1_coverage_medium_d091522a94",
            "h2p1_s2_balanced_medium_214a5381e2",
            "h2p1_s6_hop_050_medium_fb86ed3ddb",
            "h2p1_s7_hop_100_medium_b6fc36bc0f"
        )
    }
}
$CandidateJobIds = @($CandidateJobIds | ForEach-Object { [string] $_ })
if ($CandidateJobIds.Count -eq 0 -or @($CandidateJobIds | Select-Object -Unique).Count -ne $CandidateJobIds.Count) {
    throw "Candidate job IDs must be non-empty and unique"
}

$promotion = $null
if ($EvidenceClass -eq "Phase1AccuracyPromotion") {
    $promotion = Read-SharedJson $promotionPath
    if ([string] $promotion.status -ne "COMPLETE") {
        throw "Phase-1 promotion is not complete"
    }
    if ([bool] $promotion.evaluation_material_inspected) {
        throw "Development promotion claims evaluation material was inspected"
    }
    if ([bool] $promotion.weighted_composite_used) {
        throw "Development promotion unexpectedly used a weighted composite"
    }
    if (@($promotion.common_metric_priority) -contains "total_rtf") {
        throw "Contaminated accuracy-run RTF entered development promotion"
    }
}

$jobEvidence = [System.Collections.Generic.List[object]]::new()
$windowStart = $null
$windowEnd = $null
$maximumQueueBlock = 0.0
foreach ($jobId in $CandidateJobIds) {
    $manifestJob = $manifestById[$jobId]
    if ($null -eq $manifestJob) {
        throw "Candidate job is absent from the immutable job manifest: $jobId"
    }
    if ($EvidenceClass -eq "SerialResource") {
        if (-not [bool] $manifestJob.serial) {
            throw "Serial-resource candidate is not declared serial: $jobId"
        }
        if ([string] $manifestJob.job_kind -notin @(
            "resource_runtime",
            "post_selection_resource_runtime"
        )) {
            throw "Serial-resource candidate has the wrong job kind: $jobId"
        }
    }
    elseif (
        [int] $manifestJob.phase_index -ne 1 -or
        [string] $manifestJob.job_kind -ne "successive_halving_runtime" -or
        [string] $manifestJob.split -ne "development"
    ) {
        throw "Phase-1 candidate does not match the accuracy-promotion contract: $jobId"
    }
    $jobProperty = $state.jobs.PSObject.Properties[$jobId]
    if ($null -eq $jobProperty) {
        throw "Candidate job is absent from program state: $jobId"
    }
    $jobState = $jobProperty.Value
    if ([string] $jobState.state -ne "COMPLETE") {
        throw "Candidate job is not complete: $jobId"
    }
    $started = ConvertFrom-UtcJsonTimestamp $jobState.started_at_utc
    $completed = ConvertFrom-UtcJsonTimestamp $jobState.completed_at_utc
    if ($null -eq $windowStart -or $started -lt $windowStart) {
        $windowStart = $started
    }
    if ($null -eq $windowEnd -or $completed -gt $windowEnd) {
        $windowEnd = $completed
    }
    $resultPath = [IO.Path]::GetFullPath([string] $jobState.result_path)
    if (-not $resultPath.StartsWith(
        $ResultsRootPath.TrimEnd("\") + "\",
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Candidate result escaped the results root: $resultPath"
    }
    $checksumValidation = Test-ResultChecksums $resultPath
    if ([string] $checksumValidation.status -ne "VALID") {
        throw "Candidate result checksum validation failed: $jobId"
    }
    $caseRows = Read-CaseStatusRows (Join-Path $resultPath "diagnostics\case_status.jsonl")
    $audioSec = [double] (($caseRows | Measure-Object audio_duration_sec -Sum).Sum)
    $blockedTotal = [double] (($caseRows | ForEach-Object {
        $_.queue_backpressure.blocked_total_sec
    } | Measure-Object -Sum).Sum)
    $blockedMax = [double] (($caseRows | ForEach-Object {
        $_.queue_backpressure.blocked_max_sec
    } | Measure-Object -Maximum).Maximum)
    $maximumQueueBlock = [Math]::Max($maximumQueueBlock, $blockedMax)
    $droppedFrames = [int] (($caseRows | ForEach-Object {
        $_.queue_backpressure.dropped_frames
    } | Measure-Object -Sum).Sum)
    $topCases = @(
        $caseRows |
            Sort-Object { $_.queue_backpressure.blocked_max_sec } -Descending |
            Select-Object -First 8 |
            ForEach-Object {
                [ordered]@{
                    case_id = [string] $_.case_id
                    audio_duration_sec = [double] $_.audio_duration_sec
                    event_count = [int] $_.event_count
                    blocked_total_sec = [double] $_.queue_backpressure.blocked_total_sec
                    blocked_max_sec = [double] $_.queue_backpressure.blocked_max_sec
                    dropped_frames = [int] $_.queue_backpressure.dropped_frames
                }
            }
    )
    $wallSec = ($completed - $started).TotalSeconds
    $jobEvidence.Add(
        [ordered]@{
            job_id = $jobId
            phase_index = [int] $manifestJob.phase_index
            job_kind = [string] $manifestJob.job_kind
            measurement_mode = if (
                [string] $manifestJob.job_kind -in @(
                    "resource_runtime",
                    "post_selection_resource_runtime"
                )
            ) { "resources" } else { "accuracy" }
            serial_execution = [bool] $manifestJob.serial
            started_at_utc = $started.ToUniversalTime().ToString("o")
            completed_at_utc = $completed.ToUniversalTime().ToString("o")
            completed_cases = [int] $jobState.completed_cases
            completed_audio_sec = [double] $jobState.completed_audio_sec
            wall_elapsed_sec = $wallSec
            wall_rtf = if ($audioSec -gt 0.0) { $wallSec / $audioSec } else { $null }
            event_count = [int] (($caseRows | Measure-Object event_count -Sum).Sum)
            blocked_total_sec = $blockedTotal
            blocked_max_sec = $blockedMax
            cases_with_blocked_max_gt_10_sec = @($caseRows | Where-Object {
                $_.queue_backpressure.blocked_max_sec -gt 10.0
            }).Count
            cases_with_blocked_max_gt_60_sec = @($caseRows | Where-Object {
                $_.queue_backpressure.blocked_max_sec -gt 60.0
            }).Count
            dropped_frames = $droppedFrames
            result_sha256 = [string] $jobState.result_sha256
            result_path = Protect-HostText $resultPath
            checksum_validation = $checksumValidation
            largest_queue_stalls = $topCases
        }
    )
}

$queryStartLocal = $windowStart.LocalDateTime.AddMinutes(-1)
$queryEndLocal = $windowEnd.LocalDateTime.AddMinutes(1)
$esentEvents = @(
    Get-WinEvent -FilterHashtable @{
        LogName = "Application"
        ProviderName = "ESENT"
        StartTime = $queryStartLocal
        EndTime = $queryEndLocal
    } -ErrorAction SilentlyContinue |
        Where-Object { $_.Id -in 508, 510, 532, 533, 901 } |
        Sort-Object TimeCreated
)
$esentRows = @(
    $esentEvents |
        ForEach-Object { Convert-EventRecord $_ } |
        Where-Object {
            Test-WithinCandidateInterval `
                -Value $_.time_created_utc `
                -CandidateRows @($jobEvidence)
        }
)
$completedIoRows = @($esentRows | Where-Object {
    $null -ne $_.reported_io_seconds -and $_.event_id -in 508, 510
})
$maximumReportedIo = [double] (
    ($completedIoRows | ForEach-Object {
        $_.reported_io_seconds
    } | Measure-Object -Maximum).Maximum
)
$vssEvents = @(
    Get-WinEvent -FilterHashtable @{
        LogName = "Application"
        ProviderName = "VSS"
        StartTime = $queryStartLocal
        EndTime = $queryEndLocal
    } -ErrorAction SilentlyContinue |
        Where-Object { $_.Message -match "Acronis|vss_requestor" } |
        Sort-Object TimeCreated
)
$vssRows = @(
    $vssEvents |
        ForEach-Object { Convert-EventRecord $_ } |
        Where-Object {
            Test-WithinCandidateInterval `
                -Value $_.time_created_utc `
                -CandidateRows @($jobEvidence)
        }
)

$storageProviders = @(
    "disk",
    "stornvme",
    "Microsoft-Windows-StorPort",
    "Ntfs",
    "Microsoft-Windows-Ntfs",
    "volmgr",
    "Microsoft-Windows-WHEA-Logger"
)
$storageSystemEvents = [System.Collections.Generic.List[object]]::new()
$storageProviderQueryFailures = [System.Collections.Generic.List[object]]::new()
foreach ($provider in $storageProviders) {
    try {
        foreach ($event in Get-WinEvent -FilterHashtable @{
            LogName = "System"
            ProviderName = $provider
            StartTime = $queryStartLocal
            EndTime = $queryEndLocal
        } -ErrorAction Stop) {
            if ([int] $event.Level -le 3) {
                $eventRow = Convert-EventRecord $event
                if (Test-WithinCandidateInterval `
                    -Value $eventRow.time_created_utc `
                    -CandidateRows @($jobEvidence)
                ) {
                    $storageSystemEvents.Add($eventRow)
                }
            }
        }
    }
    catch {
        # Get-WinEvent reports a no-match interval as an exception even though
        # the provider query itself succeeded. Preserve only genuine query or
        # access failures; an empty warning/error interval is valid evidence.
        if ([string] $_.FullyQualifiedErrorId -notmatch "NoMatchingEventsFound") {
            $storageProviderQueryFailures.Add(
                [ordered]@{
                    provider = $provider
                    error_id = [string] $_.FullyQualifiedErrorId
                    detail = Protect-HostText $_.Exception.Message
                }
            )
        }
    }
}

$guardianRows = [System.Collections.Generic.List[object]]::new()
if (Test-Path -LiteralPath $guardianPath -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $guardianPath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        try {
            $row = $line | ConvertFrom-Json
            $at = ConvertFrom-UtcJsonTimestamp $row.at_utc
            if (Test-WithinCandidateInterval `
                -Value $at `
                -CandidateRows @($jobEvidence)
            ) {
                $guardianRows.Add(
                    [ordered]@{
                        at_utc = $at.ToUniversalTime().ToString("o")
                        action = [string] $row.action
                        capacity_risk = if ($null -ne $row.PSObject.Properties["capacity_risk"]) {
                            [string] $row.capacity_risk
                        } else { $null }
                        free_gib = if ($null -ne $row.PSObject.Properties["free_gib"]) {
                            [double] $row.free_gib
                        } else { $null }
                        job_id = if ($null -ne $row.PSObject.Properties["job_id"]) {
                            [string] $row.job_id
                        } else { $null }
                    }
                )
            }
        }
        catch {
            continue
        }
    }
}

$partition = Get-Partition -DriveLetter C
$disk = $partition | Get-Disk
$volume = Get-Volume -DriveLetter C
$backupProcesses = @(
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -match "acronis|backup_worker|cyber-protect|mms_mini|vss_requestor" } |
        Sort-Object ProcessName |
        Select-Object -ExpandProperty ProcessName -Unique
)
$os = Get-CimInstance Win32_OperatingSystem
$referenceHashes = @($jobEvidence | ForEach-Object {
    $_.checksum_validation.reference_hashes | ConvertTo-Json -Compress
} | Select-Object -Unique)
if (-not $AllowNonidenticalReferences -and $referenceHashes.Count -ne 1) {
    throw "Candidate jobs did not use identical case/reference hashes"
}

$jobIoCorrelations = [System.Collections.Generic.List[object]]::new()
foreach ($jobRow in $jobEvidence) {
    $jobStarted = ConvertFrom-UtcJsonTimestamp $jobRow.started_at_utc
    $jobCompleted = ConvertFrom-UtcJsonTimestamp $jobRow.completed_at_utc
    $jobEsent = @($esentRows | Where-Object {
        $eventTime = ConvertFrom-UtcJsonTimestamp $_.time_created_utc
        $eventTime -ge $jobStarted -and $eventTime -le $jobCompleted
    })
    $jobCompletedIo = @($jobEsent | Where-Object {
        $null -ne $_.reported_io_seconds -and $_.event_id -in 508, 510
    })
    $jobMaximumEvent = $jobCompletedIo |
        # Event rows are ordered dictionaries. Use an explicit numeric key;
        # Sort-Object's property-name form does not reliably resolve dictionary
        # keys and can silently preserve chronological order instead.
        Sort-Object { [double] $_.reported_io_seconds } -Descending |
        Select-Object -First 1
    $jobMaximumIo = if ($null -ne $jobMaximumEvent) {
        [double] $jobMaximumEvent.reported_io_seconds
    } else {
        $null
    }
    $jobVss = @($vssRows | Where-Object {
        $eventTime = ConvertFrom-UtcJsonTimestamp $_.time_created_utc
        $eventTime -ge $jobStarted -and $eventTime -le $jobCompleted
    })
    $jobGuardian = @($guardianRows | Where-Object {
        $eventTime = ConvertFrom-UtcJsonTimestamp $_.at_utc
        $eventTime -ge $jobStarted -and $eventTime -le $jobCompleted
    })
    $jobIoCorrelations.Add(
        [ordered]@{
            job_id = [string] $jobRow.job_id
            esent_event_count = $jobEsent.Count
            completed_io_event_count = $jobCompletedIo.Count
            maximum_esent_reported_io_sec = $jobMaximumIo
            maximum_esent_event_utc = if ($null -ne $jobMaximumEvent) {
                [string] $jobMaximumEvent.time_created_utc
            } else { $null }
            maximum_pipeline_blocked_put_sec = [double] $jobRow.blocked_max_sec
            absolute_maximum_difference_sec = if ($null -ne $jobMaximumIo) {
                [Math]::Abs($jobMaximumIo - [double] $jobRow.blocked_max_sec)
            } else { $null }
            acronis_vss_event_count = $jobVss.Count
            independent_storage_guardian_event_count = $jobGuardian.Count
        }
    )
}
$closestMaximumPair = $jobIoCorrelations |
    Where-Object { $null -ne $_.absolute_maximum_difference_sec } |
    Sort-Object { [double] $_.absolute_maximum_difference_sec } |
    Select-Object -First 1

$hostIoInterferenceDetected = (
    $esentRows.Count -gt 0 -or $storageSystemEvents.Count -gt 0
)
$hostIoEvidenceComplete = ($storageProviderQueryFailures.Count -eq 0)
$resourceComparisonEligible = (
    $EvidenceClass -eq "SerialResource" -and
    -not $hostIoInterferenceDetected -and
    $hostIoEvidenceComplete
)
$status = if ($EvidenceClass -eq "Phase1AccuracyPromotion") {
    "HOST_STORAGE_IO_INTERFERENCE_CONFIRMED"
}
elseif ($hostIoInterferenceDetected) {
    "SERIAL_RESOURCE_HOST_IO_CONTAMINATED"
}
elseif (-not $hostIoEvidenceComplete) {
    "SERIAL_RESOURCE_HOST_IO_UNVERIFIED"
}
else {
    "SERIAL_RESOURCE_HOST_IO_CLEAR"
}
$conclusion = if ($EvidenceClass -eq "Phase1AccuracyPromotion") {
    "Accuracy outputs remain checksum-valid; accuracy-run wall time and queue blocking are host-I/O contaminated and must not be used as serial resource evidence."
}
elseif ($hostIoInterferenceDetected) {
    "Serial resource result trees remain checksum-valid, but their wall-time, queue, RTF, CPU, and RAM evidence is host-I/O contaminated and must be replayed before final resource comparison."
}
elseif (-not $hostIoEvidenceComplete) {
    "Serial resource result trees remain checksum-valid, but one or more Windows storage-provider queries failed; resource evidence remains ineligible until a complete clean receipt is captured."
}
else {
    "No queried ESENT or storage warning/error overlapped the exact serial resource intervals; the checksum-valid serial resource evidence remains eligible for final comparison."
}
$promotionEvidence = if ($EvidenceClass -eq "Phase1AccuracyPromotion") {
    [ordered]@{
        decision_path = "%WORKSPACE%\promotions\phase_1_full.json"
        decision_sha256 = Get-Sha256 $promotionPath
        selected_candidates = @($promotion.selected_candidates)
        pareto_frontier = @($promotion.pareto_frontier)
        common_metric_priority = @($promotion.common_metric_priority)
        evaluation_material_inspected = [bool] $promotion.evaluation_material_inspected
        weighted_composite_used = [bool] $promotion.weighted_composite_used
    }
}
else {
    $null
}

$document = [ordered]@{
    schema_version = "h2-host-io-interference.v1"
    status = $status
    evidence_class = $EvidenceClass
    generated_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
    protocol_id = [string] $state.protocol_id
    protocol_sha256 = [string] $state.protocol_sha256
    job_manifest_sha256 = [string] $state.job_manifest_sha256
    candidate_job_ids = @($CandidateJobIds)
    evidence_window = [ordered]@{
        start_utc = $windowStart.ToUniversalTime().ToString("o")
        end_utc = $windowEnd.ToUniversalTime().ToString("o")
        query_start_local = $queryStartLocal.ToString("o")
        query_end_local = $queryEndLocal.ToString("o")
    }
    scientific_interpretation = [ordered]@{
        accuracy_metrics_eligible = $true
        development_promotion_eligible = ($EvidenceClass -eq "Phase1AccuracyPromotion")
        operational_wall_time_eligible = $resourceComparisonEligible
        resource_comparison_eligible = $resourceComparisonEligible
        total_rtf_entered_promotion = $false
        scientific_results_or_policies_modified = $false
        inference_rerun = $false
        queue_policy = "block"
        dropped_frames_total = [int] (($jobEvidence | ForEach-Object {
            $_.dropped_frames
        } | Measure-Object -Sum).Sum)
        host_io_interference_detected = $hostIoInterferenceDetected
        host_io_evidence_complete = $hostIoEvidenceComplete
        conclusion = $conclusion
        causal_attribution = "Acronis VSS/backup activity was temporally coincident, but this receipt does not claim it was the sole hardware or software cause."
    }
    correlation = [ordered]@{
        esent_hung_io_event_count = $esentRows.Count
        esent_completed_io_event_count = $completedIoRows.Count
        maximum_esent_reported_io_sec = $maximumReportedIo
        maximum_pipeline_blocked_put_sec = $maximumQueueBlock
        absolute_maximum_difference_sec = [Math]::Abs($maximumReportedIo - $maximumQueueBlock)
        acronis_vss_event_count = $vssRows.Count
        storage_driver_warning_or_error_count = $storageSystemEvents.Count
        independent_storage_guardian_event_count = $guardianRows.Count
        per_job = @($jobIoCorrelations)
        closest_maximum_duration_pair = $closestMaximumPair
    }
    promotion = $promotionEvidence
    candidate_jobs = @($jobEvidence)
    windows_evidence = [ordered]@{
        esent_events = $esentRows
        acronis_vss_events = $vssRows
        storage_driver_warnings_or_errors = @($storageSystemEvents)
        storage_provider_query_failures = @($storageProviderQueryFailures)
        storage_guardian_events = @($guardianRows)
        active_backup_process_names_at_capture = $backupProcesses
    }
    host_storage = [ordered]@{
        drive = "C:"
        disk_number = [int] $disk.Number
        disk_model = [string] $disk.FriendlyName
        bus_type = [string] $disk.BusType
        health_status = [string] $disk.HealthStatus
        operational_status = @($disk.OperationalStatus | ForEach-Object { [string] $_ })
        volume_health_status = [string] $volume.HealthStatus
        volume_operational_status = @($volume.OperationalStatus | ForEach-Object { [string] $_ })
        free_bytes_at_capture = [int64] $volume.SizeRemaining
        size_bytes = [int64] $volume.Size
        reliability_counters = "UNAVAILABLE_WITHOUT_ELEVATED_CIM_ACCESS"
    }
    host_os = [ordered]@{
        caption = [string] $os.Caption
        version = [string] $os.Version
        build_number = [string] $os.BuildNumber
    }
    provenance = [ordered]@{
        collector = "scripts/capture_h2_host_io_interference.ps1"
        collector_sha256 = Get-Sha256 $PSCommandPath
        evidence_class = $EvidenceClass
        program_state_sha256_at_capture = Get-Sha256 $statePath
        job_manifest_embedded_self_hash_matches_state = $true
        job_manifest_file_sha256 = $jobManifestFileSha256
        all_candidate_result_checksums_verified = $true
        identical_case_reference_hashes_verified = ($referenceHashes.Count -eq 1)
        nonidentical_references_explicitly_allowed = [bool] $AllowNonidenticalReferences
        windows_event_queries = @(
            "Application/ESENT IDs 508,510,532,533,901",
            "Application/VSS messages containing Acronis or vss_requestor",
            "System storage-provider warnings and errors"
        )
        host_paths_sanitized = $true
    }
}

Write-JsonAtomic -LiteralPath $OutputPath -Value $document
$outputSha = Get-Sha256 $OutputPath
Write-Output ("HOST_IO_RECEIPT={0}" -f $OutputPath)
Write-Output ("SHA256={0}" -f $outputSha)
Write-Output ("STATUS={0}" -f $document.status)
Write-Output ("ESENT_EVENTS={0}" -f $esentRows.Count)
Write-Output ("MAX_ESENT_IO_SEC={0}" -f $maximumReportedIo)
Write-Output ("MAX_PIPELINE_BLOCK_SEC={0}" -f $maximumQueueBlock)
