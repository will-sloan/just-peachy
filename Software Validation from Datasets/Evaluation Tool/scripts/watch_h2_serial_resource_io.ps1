[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $Workspace,

    [Parameter(Mandatory = $true)]
    [string] $ResultsRoot,

    [ValidateRange(10, 3600)]
    [int] $IntervalSeconds = 60,

    [switch] $Once
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

function Write-WatcherLog {
    param(
        [Parameter(Mandatory = $true)][string] $LiteralPath,
        [Parameter(Mandatory = $true)] $Value
    )

    $parent = Split-Path -Parent $LiteralPath
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $line = ($Value | ConvertTo-Json -Depth 8 -Compress) + [Environment]::NewLine
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($line)
    $sharing = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $stream = [IO.FileStream]::new(
        $LiteralPath,
        [IO.FileMode]::Append,
        [IO.FileAccess]::Write,
        $sharing
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }
}

function Test-ReceiptCurrent {
    param(
        [Parameter(Mandatory = $true)][string] $LiteralPath,
        [Parameter(Mandatory = $true)][string] $ProtocolId,
        [Parameter(Mandatory = $true)][string[]] $JobIds,
        [Parameter(Mandatory = $true)][string] $CollectorSha256
    )

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        return $false
    }
    try {
        $receipt = Read-SharedJson $LiteralPath
        $actualIds = @($receipt.candidate_job_ids | ForEach-Object { [string] $_ } | Sort-Object)
        $expectedIds = @($JobIds | Sort-Object)
        return (
            [string] $receipt.schema_version -eq "h2-host-io-interference.v1" -and
            [string] $receipt.evidence_class -eq "SerialResource" -and
            [string] $receipt.protocol_id -eq $ProtocolId -and
            [string] $receipt.status -in @(
                "SERIAL_RESOURCE_HOST_IO_CLEAR",
                "SERIAL_RESOURCE_HOST_IO_CONTAMINATED",
                "SERIAL_RESOURCE_HOST_IO_UNVERIFIED"
            ) -and
            [string] $receipt.provenance.collector_sha256 -eq $CollectorSha256 -and
            ($actualIds -join "`n") -eq ($expectedIds -join "`n")
        )
    }
    catch {
        return $false
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

$Collector = Join-Path $PSScriptRoot "capture_h2_host_io_interference.ps1"
if (-not (Test-Path -LiteralPath $Collector -PathType Leaf)) {
    throw "Host-I/O collector is missing: $Collector"
}
$StatePath = Join-Path $WorkspacePath "program_state.json"
$ManifestPath = Join-Path $WorkspacePath "job_manifest.json"
$ReceiptRoot = Join-Path $WorkspacePath "diagnostics\host_io_interference"
$LogPath = Join-Path $WorkspacePath "logs\serial-resource-host-io-watcher.jsonl"

while ($true) {
    # Recompute on every pass so a diagnostic-only collector hardening made
    # during a long campaign cannot leave this watcher comparing future
    # receipts against a stale source identity.
    $CollectorSha256 = Get-Sha256 $Collector
    $state = Read-SharedJson $StatePath
    $manifest = Read-SharedJson $ManifestPath
    if ([string] $state.protocol_id -ne [string] $manifest.protocol_id) {
        throw "Program state and job manifest protocol IDs differ"
    }
    $groups = @(
        [ordered]@{
            id = "phase2_matched_redim"
            output = Join-Path $ReceiptRoot "serial_resource_phase2_redim_host_io.json"
            jobs = @(
                $manifest.jobs |
                    Where-Object {
                        [int] $_.phase_index -eq 2 -and
                        [bool] $_.serial -and
                        [string] $_.job_kind -eq "resource_runtime"
                    } |
                    Select-Object -ExpandProperty job_id
            )
        },
        [ordered]@{
            id = "phase6_selected_modes"
            output = Join-Path $ReceiptRoot "serial_resource_phase6_modes_host_io.json"
            jobs = @(
                $manifest.jobs |
                    Where-Object {
                        [int] $_.phase_index -eq 6 -and
                        [bool] $_.serial -and
                        [string] $_.job_kind -eq "post_selection_resource_runtime"
                    } |
                    Select-Object -ExpandProperty job_id
            )
        }
    )
    if (@($groups | Where-Object { @($_.jobs).Count -eq 0 }).Count -gt 0) {
        throw "The immutable job manifest lacks one or more serial-resource groups"
    }

    $completeGroups = 0
    foreach ($group in $groups) {
        $jobIds = @($group.jobs | ForEach-Object { [string] $_ })
        $states = @(
            $jobIds | ForEach-Object {
                $property = $state.jobs.PSObject.Properties[$_]
                if ($null -eq $property) { "ABSENT" } else { [string] $property.Value.state }
            }
        )
        $allComplete = @($states | Where-Object { $_ -ne "COMPLETE" }).Count -eq 0
        if (-not $allComplete) {
            Write-Output ("SERIAL_IO_WAITING={0}; states={1}" -f $group.id, ($states -join ","))
            continue
        }
        try {
            if (-not (Test-ReceiptCurrent `
                -LiteralPath $group.output `
                -ProtocolId ([string] $state.protocol_id) `
                -JobIds $jobIds `
                -CollectorSha256 $CollectorSha256
            )) {
                $collectorOutput = @(
                    & $Collector `
                        -Workspace $WorkspacePath `
                        -ResultsRoot $ResultsRootPath `
                        -EvidenceClass SerialResource `
                        -CandidateJobIds $jobIds `
                        -OutputPath $group.output
                )
                Write-WatcherLog -LiteralPath $LogPath -Value ([ordered]@{
                    schema_version = "h2-serial-resource-host-io-watcher.v1"
                    recorded_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
                    group_id = [string] $group.id
                    status = "RECEIPT_CAPTURED"
                    candidate_job_ids = $jobIds
                    receipt_path = [string] $group.output
                    receipt_sha256 = Get-Sha256 $group.output
                    collector_output = $collectorOutput
                })
            }
            $receipt = Read-SharedJson $group.output
            Write-Output ("SERIAL_IO_RECEIPT={0}; status={1}" -f $group.output, $receipt.status)
            $completeGroups += 1
        }
        catch {
            Write-WatcherLog -LiteralPath $LogPath -Value ([ordered]@{
                schema_version = "h2-serial-resource-host-io-watcher.v1"
                recorded_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
                group_id = [string] $group.id
                status = "RECEIPT_CAPTURE_FAILED_WILL_RETRY"
                candidate_job_ids = $jobIds
                error_id = [string] $_.FullyQualifiedErrorId
                detail = [string] $_.Exception.Message
            })
            Write-Output ("SERIAL_IO_RETRY={0}; error={1}" -f $group.id, $_.Exception.Message)
        }
    }

    if ($completeGroups -eq $groups.Count) {
        Write-WatcherLog -LiteralPath $LogPath -Value ([ordered]@{
            schema_version = "h2-serial-resource-host-io-watcher.v1"
            recorded_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
            status = "ALL_SERIAL_RESOURCE_RECEIPTS_COMPLETE"
            protocol_id = [string] $state.protocol_id
        })
        break
    }
    if ($Once) {
        break
    }
    if ([string] $state.status -in @("FAILED", "BLOCKED", "STOPPED")) {
        Write-WatcherLog -LiteralPath $LogPath -Value ([ordered]@{
            schema_version = "h2-serial-resource-host-io-watcher.v1"
            recorded_at_utc = [DateTimeOffset]::UtcNow.ToString("o")
            status = "PROGRAM_TERMINATED_BEFORE_SERIAL_RESOURCE_RECEIPTS"
            program_status = [string] $state.status
        })
        break
    }
    Start-Sleep -Seconds $IntervalSeconds
}
