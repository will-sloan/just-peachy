[CmdletBinding()]
param(
    [string]$Workspace,
    [ValidateRange(10,3600)]
    [int]$IntervalSeconds = 30,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($Workspace)) {
    $Workspace = Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
}
$Workspace = [IO.Path]::GetFullPath($Workspace)
if (-not (Test-Path -LiteralPath $Workspace -PathType Container)) {
    throw "H2 workspace is unavailable: $Workspace"
}
if ([IO.Path]::GetPathRoot($Workspace).TrimEnd('\').ToUpperInvariant() -ne 'C:') {
    throw 'The H2 milestone notifier is restricted to the C: campaign workspace.'
}

$ProgramStatePath = Join-Path $Workspace 'program_state.json'
$MilestonesPath = Join-Path $Workspace 'milestones.jsonl'
$RuntimeRoot = Join-Path $Workspace 'milestone_notifier'
$NotifierStatePath = Join-Path $RuntimeRoot 'notifier_state.json'
$EventLogPath = Join-Path $RuntimeRoot 'notifier_events.jsonl'
$LockPath = Join-Path $RuntimeRoot 'notifier.lock'

function Read-H2TextSharedDelete {
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
            return $Reader.ReadToEnd()
        }
        finally {
            $Reader.Dispose()
        }
    }
    finally {
        $Stream.Dispose()
    }
}

function Read-H2JsonSharedDelete {
    param([string]$Path)
    return (Read-H2TextSharedDelete -Path $Path) | ConvertFrom-Json
}

function Read-Milestones {
    if (-not (Test-Path -LiteralPath $MilestonesPath -PathType Leaf)) {
        return @()
    }
    return @(
        [regex]::Split(
            (Read-H2TextSharedDelete -Path $MilestonesPath),
            '\r?\n'
        ) |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            ForEach-Object { $_ | ConvertFrom-Json }
    )
}

function Write-NotifierState {
    param(
        [string[]]$SeenMilestoneIds,
        [string]$LastProgramStatus
    )
    $Payload = [ordered]@{
        schema_version = 'h2-milestone-notifier-state.v1'
        updated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
        workspace = $Workspace
        seen_milestone_ids = @($SeenMilestoneIds | Sort-Object -Unique)
        last_program_status = $LastProgramStatus
    }
    $Json = $Payload | ConvertTo-Json -Depth 8
    $Temporary = Join-Path $RuntimeRoot ('.notifier_state.' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($Temporary, $Json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $Temporary -Destination $NotifierStatePath -Force
    }
    finally {
        if (Test-Path -LiteralPath $Temporary -PathType Leaf) {
            Remove-Item -LiteralPath $Temporary -Force -ErrorAction SilentlyContinue
        }
    }
}

function Write-NotifierEvent {
    param(
        [string]$Status,
        [string]$Detail,
        [string]$MilestoneId = ''
    )
    $Event = [ordered]@{
        schema_version = 'h2-milestone-notifier-event.v1'
        timestamp_utc = [DateTimeOffset]::UtcNow.ToString('o')
        status = $Status
        milestone_id = if ([string]::IsNullOrWhiteSpace($MilestoneId)) { $null } else { $MilestoneId }
        detail = $Detail
    }
    ($Event | ConvertTo-Json -Compress) | Add-Content -LiteralPath $EventLogPath -Encoding UTF8
}

function Play-MilestoneSound {
    param([string]$Kind)
    if ($Kind -eq 'HELDOUT_OPENED') {
        [System.Media.SystemSounds]::Exclamation.Play()
    }
    elseif ($Kind -eq 'PROGRAM_COMPLETE') {
        [System.Media.SystemSounds]::Asterisk.Play()
        Start-Sleep -Milliseconds 400
        [System.Media.SystemSounds]::Asterisk.Play()
    }
    else {
        [System.Media.SystemSounds]::Asterisk.Play()
    }
}

$ExistingMilestones = @(Read-Milestones)
$CurrentStatus = if (Test-Path -LiteralPath $ProgramStatePath -PathType Leaf) {
    [string]((Read-H2JsonSharedDelete -Path $ProgramStatePath).status)
}
else {
    'NOT_YET_AVAILABLE'
}

if ($DryRun) {
    [ordered]@{
        schema_version = 'h2-milestone-notifier-dry-run.v1'
        status = 'PASS'
        workspace = $Workspace
        program_state_path = $ProgramStatePath
        milestones_path = $MilestonesPath
        current_program_status = $CurrentStatus
        existing_milestone_count = $ExistingMilestones.Count
        interval_seconds = $IntervalSeconds
        scientific_files_modified = $false
    } | ConvertTo-Json -Depth 6
    exit 0
}

New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null

# FileShare.None gives the helper a cross-process single-instance lock. The
# lock file is metadata only and is never part of scientific evidence.
try {
    $LockHandle = [IO.File]::Open(
        $LockPath,
        [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
}
catch {
    throw "Another H2 milestone notifier already owns $LockPath"
}

try {
    $Seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    if (Test-Path -LiteralPath $NotifierStatePath -PathType Leaf) {
        $Prior = Read-H2JsonSharedDelete -Path $NotifierStatePath
        if ([string]$Prior.schema_version -ne 'h2-milestone-notifier-state.v1') {
            throw 'Existing H2 milestone notifier state has an unsupported schema.'
        }
        foreach ($Id in @($Prior.seen_milestone_ids)) {
            [void]$Seen.Add([string]$Id)
        }
    }
    else {
        # Establish the current durable milestones as the baseline. Only future
        # events should alert when a notifier is attached mid-campaign.
        foreach ($Milestone in $ExistingMilestones) {
            [void]$Seen.Add([string]$Milestone.milestone_id)
        }
        Write-NotifierState -SeenMilestoneIds @($Seen) -LastProgramStatus $CurrentStatus
    }
    Write-NotifierEvent -Status 'STARTED' -Detail (
        "baseline_milestones=$($Seen.Count); current_program_status=$CurrentStatus"
    )

    $LastStatus = $CurrentStatus
    while ($true) {
        $Milestones = @(Read-Milestones)
        foreach ($Milestone in $Milestones) {
            $Id = [string]$Milestone.milestone_id
            if ([string]::IsNullOrWhiteSpace($Id) -or $Seen.Contains($Id)) {
                continue
            }
            $Kind = [string]$Milestone.kind
            $Detail = [string]$Milestone.detail
            Play-MilestoneSound -Kind $Kind
            Write-NotifierEvent -Status 'MILESTONE' -Detail "$Kind - $Detail" -MilestoneId $Id
            [void]$Seen.Add($Id)
        }

        $Status = if (Test-Path -LiteralPath $ProgramStatePath -PathType Leaf) {
            [string]((Read-H2JsonSharedDelete -Path $ProgramStatePath).status)
        }
        else {
            'NOT_YET_AVAILABLE'
        }
        if ($Status -ne $LastStatus) {
            Write-NotifierEvent -Status 'PROGRAM_STATUS' -Detail "$LastStatus -> $Status"
            $LastStatus = $Status
        }
        Write-NotifierState -SeenMilestoneIds @($Seen) -LastProgramStatus $Status

        if ($Status -eq 'COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM') {
            Play-MilestoneSound -Kind 'PROGRAM_COMPLETE'
            Write-NotifierEvent -Status 'COMPLETE' -Detail $Status
            exit 0
        }
        if ($Status -in @('FAILED', 'BLOCKED_SCIENTIFIC_RUN', 'BLOCKED_OTHER')) {
            [System.Media.SystemSounds]::Hand.Play()
            Write-NotifierEvent -Status 'CAMPAIGN_NOT_COMPLETE' -Detail $Status
            exit 2
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
}
finally {
    if ($null -ne $LockHandle) {
        $LockHandle.Dispose()
    }
}
