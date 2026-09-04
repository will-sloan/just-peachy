[CmdletBinding()]
param(
    [string] $Workspace,
    [string] $ResultsRoot,
    [string] $SummaryRoot,
    [ValidateRange(10, 3600)]
    [int] $IntervalSeconds = 60,
    [ValidateRange(1, 1024)]
    [double] $MinimumFreeGiB = 35,
    [ValidateRange(1, 1440)]
    [int] $QuietWindowMinutes = 15,
    [ValidateRange(0, 3600)]
    [int] $CooldownSeconds = 60,
    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$ReplayTool = Join-Path $PSScriptRoot 'replay_h2_phase2_serial_resources.py'
$UiLatencyTool = Join-Path $PSScriptRoot 'measure_h2_ui_event_latency.py'
$Config = Join-Path $ToolRoot 'configs\automated_evaluation\h2_product_program.v17.yaml'

if ([string]::IsNullOrWhiteSpace($Workspace)) {
    $Workspace = Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
}
if ([string]::IsNullOrWhiteSpace($ResultsRoot)) {
    $ResultsRoot = Join-Path $ToolRoot 'JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17'
}
if ([string]::IsNullOrWhiteSpace($SummaryRoot)) {
    $SummaryRoot = Join-Path $ToolRoot 'JustPeachyResearchSummaries\h2_complete_product_pipeline_v17'
}

$Workspace = [IO.Path]::GetFullPath($Workspace)
$ResultsRoot = [IO.Path]::GetFullPath($ResultsRoot)
$SummaryRoot = [IO.Path]::GetFullPath($SummaryRoot)
$StatePath = Join-Path $Workspace 'program_state.json'
$EngineeringRoot = Join-Path $Workspace 'engineering_validation'
$UiReceiptPath = Join-Path $EngineeringRoot 'ui_event_latency_receipt.json'
$CompletionPath = Join-Path $EngineeringRoot 'postcampaign_engineering_evidence.json'
$LogPath = Join-Path $Workspace 'logs\postcampaign-engineering-watcher.jsonl'

function Assert-H2CDrivePath {
    param([Parameter(Mandatory = $true)][string] $LiteralPath)

    if ([IO.Path]::GetPathRoot($LiteralPath).TrimEnd('\').ToUpperInvariant() -ne 'C:') {
        throw "H2 post-campaign path must remain on C:: $LiteralPath"
    }
}

function Read-H2JsonShared {
    param([Parameter(Mandatory = $true)][string] $LiteralPath)

    $sharing = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $stream = [IO.File]::Open(
        $LiteralPath,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        $sharing
    )
    try {
        $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::UTF8)
        try {
            return $reader.ReadToEnd() | ConvertFrom-Json
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Get-H2Sha256 {
    param([Parameter(Mandatory = $true)][string] $LiteralPath)

    return (Get-FileHash -LiteralPath $LiteralPath -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-H2JsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string] $LiteralPath,
        [Parameter(Mandatory = $true)] $Value
    )

    $parent = Split-Path -Parent $LiteralPath
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $temporary = Join-Path $parent (
        [IO.Path]::GetFileName($LiteralPath) + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    )
    $json = ($Value | ConvertTo-Json -Depth 32) + [Environment]::NewLine
    [IO.File]::WriteAllText($temporary, $json, [Text.UTF8Encoding]::new($false))
    try {
        if (Test-Path -LiteralPath $LiteralPath -PathType Leaf) {
            [IO.File]::Replace($temporary, $LiteralPath, $null)
        }
        else {
            [IO.File]::Move($temporary, $LiteralPath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function Write-H2WatcherEvent {
    param(
        [Parameter(Mandatory = $true)][string] $Status,
        [Parameter(Mandatory = $true)][string] $Detail
    )

    $event = [ordered]@{
        schema_version = 'h2-postcampaign-engineering-watcher.v1'
        timestamp_utc = [DateTimeOffset]::UtcNow.ToString('o')
        status = $Status
        detail = $Detail
    }
    $parent = Split-Path -Parent $LogPath
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    ($event | ConvertTo-Json -Compress) | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

function Invoke-H2JsonTool {
    param([Parameter(Mandatory = $true)][string[]] $Arguments)

    $output = @(& $Python @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    $raw = ($output | ForEach-Object { [string] $_ }) -join [Environment]::NewLine
    $payload = $null
    try {
        $payload = $raw | ConvertFrom-Json
    }
    catch {
        $payload = $null
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Raw = $raw
        Payload = $payload
    }
}

function Find-H2EligibleReplay {
    $parent = Split-Path -Parent $SummaryRoot
    $prefix = [IO.Path]::GetFileName($SummaryRoot) + '_resource_replay_quiet'
    $candidates = @(
        Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name.StartsWith($prefix, [StringComparison]::Ordinal) } |
            Sort-Object Name
    )
    foreach ($candidate in $candidates) {
        $comparisonPath = Join-Path $candidate.FullName 'resource_comparison.json'
        if (-not (Test-Path -LiteralPath $comparisonPath -PathType Leaf)) {
            continue
        }
        try {
            $comparison = Read-H2JsonShared -LiteralPath $comparisonPath
            if (
                [string] $comparison.schema_version -eq 'h2-phase2-quiet-resource-comparison.v1' -and
                [bool] $comparison.eligible_for_final_resource_ranking -and
                [string] $comparison.host_io_status -eq 'SERIAL_RESOURCE_HOST_IO_CLEAR'
            ) {
                return [pscustomobject]@{
                    AttemptId = 'quiet' + $candidate.Name.Substring($prefix.Length)
                    ComparisonPath = $comparisonPath
                    Comparison = $comparison
                }
            }
        }
        catch {
            Write-H2WatcherEvent -Status 'REPLAY_COMPARISON_INVALID' -Detail (
                "$comparisonPath; $($_.Exception.Message)"
            )
        }
    }
    return $null
}

function Select-H2ReplayAttemptId {
    $workspaceParent = Split-Path -Parent $Workspace
    $workspaceName = [IO.Path]::GetFileName($Workspace)
    $summaryParent = Split-Path -Parent $SummaryRoot
    $summaryName = [IO.Path]::GetFileName($SummaryRoot)
    foreach ($index in 1..999) {
        $attemptId = 'quiet{0:D2}' -f $index
        $attemptWorkspace = Join-Path $workspaceParent ($workspaceName + '_resource_replay_' + $attemptId)
        $attemptSummary = Join-Path $summaryParent (
            $summaryName + '_resource_replay_' + $attemptId
        )
        $comparisonPath = Join-Path $attemptSummary 'resource_comparison.json'
        if (-not (Test-Path -LiteralPath $comparisonPath -PathType Leaf)) {
            return $attemptId
        }
        $comparison = Read-H2JsonShared -LiteralPath $comparisonPath
        if ([bool] $comparison.eligible_for_final_resource_ranking) {
            return $attemptId
        }
        if (-not (Test-Path -LiteralPath $attemptWorkspace -PathType Container)) {
            return $attemptId
        }
    }
    throw 'All 999 deterministic quiet replay attempt IDs are occupied.'
}

foreach ($path in @($Workspace, $ResultsRoot, $SummaryRoot, $Config)) {
    Assert-H2CDrivePath -LiteralPath $path
}
foreach ($required in @($Python, $ReplayTool, $UiLatencyTool, $Config, $Workspace, $ResultsRoot, $SummaryRoot)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required H2 post-campaign path is unavailable: $required"
    }
}

if ($DryRun) {
    $state = if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
        Read-H2JsonShared -LiteralPath $StatePath
    }
    else {
        $null
    }
    [ordered]@{
        schema_version = 'h2-postcampaign-engineering-watcher-dry-run.v1'
        status = 'PASS'
        mutates_campaign = $false
        starts_neural_inference = $false
        current_program_status = if ($null -eq $state) { 'NOT_AVAILABLE' } else { [string] $state.status }
        workspace = $Workspace
        results_root = $ResultsRoot
        summary_root = $SummaryRoot
        python = $Python
        replay_tool = $ReplayTool
        replay_tool_sha256 = Get-H2Sha256 -LiteralPath $ReplayTool
        ui_latency_tool = $UiLatencyTool
        ui_latency_tool_sha256 = Get-H2Sha256 -LiteralPath $UiLatencyTool
        ui_receipt = $UiReceiptPath
        completion_receipt = $CompletionPath
        order = @(
            'wait_for_complete_h2_product_pipeline_program',
            'wait_for_quiet_host_and_create_eligible_phase2_r1_r2_replay',
            'measure_and_validate_controlled_ui_event_latency',
            'allow_existing_final_package_watcher_to_augment'
        )
    } | ConvertTo-Json -Depth 8
    exit 0
}

Write-H2WatcherEvent -Status 'STARTED' -Detail (
    "workspace=$Workspace; interval_seconds=$IntervalSeconds; no_time_limit=true"
)

while ($true) {
    try {
        $state = Read-H2JsonShared -LiteralPath $StatePath
        $status = [string] $state.status
        if ($status -ne 'COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM') {
            # Generic BLOCKED is recoverable orchestration state in this
            # campaign (including the checksum-bound selector handoff). Only
            # explicit terminal scientific/final blockers or a user stop end
            # this post-campaign waiter.
            if ($status -in @('FAILED', 'BLOCKED_OTHER', 'BLOCKED_SCIENTIFIC_RUN', 'STOPPED')) {
                Write-H2WatcherEvent -Status 'SOURCE_PROGRAM_TERMINAL_NOT_COMPLETE' -Detail "program_status=$status"
                exit 2
            }
            Start-Sleep -Seconds $IntervalSeconds
            continue
        }

        $eligibleReplay = Find-H2EligibleReplay
        if ($null -eq $eligibleReplay) {
            $attemptId = Select-H2ReplayAttemptId
            $commonArguments = @(
                '--attempt-id', $attemptId,
                '--source-workspace', $Workspace,
                '--source-results-root', $ResultsRoot,
                '--source-summary-root', $SummaryRoot,
                '--config', $Config,
                '--minimum-free-gib', [string] $MinimumFreeGiB,
                '--quiet-window-minutes', [string] $QuietWindowMinutes,
                '--cooldown-sec', [string] $CooldownSeconds
            )
            $preflight = Invoke-H2JsonTool -Arguments (@($ReplayTool, 'preflight') + $commonArguments)
            if (
                $preflight.ExitCode -ne 0 -or
                $null -eq $preflight.Payload -or
                [string] $preflight.Payload.status -ne 'ELIGIBLE'
            ) {
                Write-H2WatcherEvent -Status 'WAITING_FOR_QUIET_REPLAY_PREFLIGHT' -Detail (
                    "attempt=$attemptId; exit=$($preflight.ExitCode); " +
                    $preflight.Raw.Substring(0, [Math]::Min(4000, $preflight.Raw.Length))
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
            Write-H2WatcherEvent -Status 'QUIET_REPLAY_STARTING' -Detail "attempt=$attemptId"
            $replay = Invoke-H2JsonTool -Arguments (@($ReplayTool, 'run') + $commonArguments)
            if ($replay.ExitCode -ne 0 -or $null -eq $replay.Payload) {
                Write-H2WatcherEvent -Status 'QUIET_REPLAY_RETRY_REQUIRED' -Detail (
                    "attempt=$attemptId; exit=$($replay.ExitCode); " +
                    $replay.Raw.Substring(0, [Math]::Min(4000, $replay.Raw.Length))
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
            $eligibleReplay = Find-H2EligibleReplay
            if ($null -eq $eligibleReplay) {
                Write-H2WatcherEvent -Status 'QUIET_REPLAY_NOT_ELIGIBLE' -Detail (
                    "attempt=$attemptId; status=$([string] $replay.Payload.status)"
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
            Write-H2WatcherEvent -Status 'QUIET_REPLAY_ELIGIBLE' -Detail (
                "attempt=$($eligibleReplay.AttemptId); comparison=$($eligibleReplay.ComparisonPath)"
            )
        }

        $uiValid = $false
        if (Test-Path -LiteralPath $UiReceiptPath -PathType Leaf) {
            $validation = Invoke-H2JsonTool -Arguments @($UiLatencyTool, '--validate', $UiReceiptPath)
            $uiValid = $validation.ExitCode -eq 0 -and $null -ne $validation.Payload -and [string] $validation.Payload.status -eq 'VALID'
            if (-not $uiValid) {
                Write-H2WatcherEvent -Status 'UI_RECEIPT_INVALID' -Detail (
                    $validation.Raw.Substring(0, [Math]::Min(4000, $validation.Raw.Length))
                )
            }
        }
        if (-not $uiValid) {
            Write-H2WatcherEvent -Status 'UI_LATENCY_STARTING' -Detail 'samples=100; warmup=10; neural_inference=false'
            $measurement = Invoke-H2JsonTool -Arguments @(
                $UiLatencyTool,
                '--workspace', $Workspace,
                '--output', $UiReceiptPath,
                '--samples', '100',
                '--warmup', '10',
                '--timeout-sec', '5'
            )
            if (
                $measurement.ExitCode -ne 0 -or
                $null -eq $measurement.Payload -or
                [string] $measurement.Payload.status -ne 'VALID'
            ) {
                Write-H2WatcherEvent -Status 'UI_LATENCY_RETRY_REQUIRED' -Detail (
                    "exit=$($measurement.ExitCode); " +
                    $measurement.Raw.Substring(0, [Math]::Min(4000, $measurement.Raw.Length))
                )
                Start-Sleep -Seconds $IntervalSeconds
                continue
            }
        }

        $uiReceipt = Read-H2JsonShared -LiteralPath $UiReceiptPath
        $completion = [ordered]@{
            schema_version = 'h2-postcampaign-engineering-evidence.v1'
            status = 'COMPLETE'
            completed_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
            source_program_status = $status
            source_program_state_sha256 = Get-H2Sha256 -LiteralPath $StatePath
            scientific_results_or_policy_changed = $false
            phase2_quiet_replay = [ordered]@{
                attempt_id = [string] $eligibleReplay.AttemptId
                comparison_path = [string] $eligibleReplay.ComparisonPath
                comparison_file_sha256 = Get-H2Sha256 -LiteralPath $eligibleReplay.ComparisonPath
                comparison_sha256 = [string] $eligibleReplay.Comparison.comparison_sha256
                eligible_for_final_resource_ranking = $true
                host_io_status = [string] $eligibleReplay.Comparison.host_io_status
            }
            controlled_ui_latency = [ordered]@{
                receipt_path = $UiReceiptPath
                receipt_file_sha256 = Get-H2Sha256 -LiteralPath $UiReceiptPath
                receipt_sha256 = [string] $uiReceipt.receipt_sha256
                neural_inference_executed = $false
                metrics = $uiReceipt.metrics
            }
            watcher = [ordered]@{
                path = $MyInvocation.MyCommand.Path
                sha256 = Get-H2Sha256 -LiteralPath $MyInvocation.MyCommand.Path
                no_automatic_time_limit = $true
            }
        }
        Write-H2JsonAtomic -LiteralPath $CompletionPath -Value $completion
        Write-H2WatcherEvent -Status 'COMPLETE' -Detail (
            "completion_receipt=$CompletionPath; ui_receipt=$UiReceiptPath; " +
            "replay=$($eligibleReplay.ComparisonPath)"
        )
        [System.Media.SystemSounds]::Asterisk.Play()
        exit 0
    }
    catch {
        Write-H2WatcherEvent -Status 'RETRY_AFTER_ERROR' -Detail (
            "$($_.FullyQualifiedErrorId); $($_.Exception.Message)"
        )
        Start-Sleep -Seconds $IntervalSeconds
    }
}
