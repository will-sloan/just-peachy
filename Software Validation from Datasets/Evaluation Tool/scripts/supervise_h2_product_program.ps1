[CmdletBinding()]
param(
    [string]$Workspace,
    [string]$ResultsRoot,
    [string]$SummaryRoot,
    [string]$Config,
    [ValidateRange(5,300)]
    [int]$PollSeconds = 20,
    [ValidateRange(120,600)]
    [int]$LeaseRecoverySeconds = 130,
    [ValidateRange(1,20)]
    [int]$MaximumConsecutiveRecoveries = 5,
    [ValidateRange(0,10)]
    [int]$MaximumUnclassifiedRecoveries = 2,
    [ValidateRange(60,3600)]
    [int]$HealthyProgressResetSeconds = 600,
    [ValidateRange(5,3600)]
    [int]$StorageGuardianIntervalSeconds = 300,
    [ValidateRange(1,10000)]
    [double]$MinimumFreeGiB = 35,
    [ValidateRange(1,10000)]
    [double]$TargetFreeGiB = 80,
    [switch]$DisableStorageGuardian,
    [switch]$DisableSelectorCorrection,
    [switch]$SelectorCorrectionPreflightOnly,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Runner = Join-Path $PSScriptRoot 'run_h2_product_program.ps1'
$StorageGuardianRunner = Join-Path $PSScriptRoot 'run_h2_storage_guardian.ps1'
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
$ProgramStatePath = Join-Path $Workspace 'program_state.json'
$ProgressPath = Join-Path $Workspace 'campaign_progress.json'
$StopRequestPath = Join-Path $Workspace 'stop_request.json'
$LogRoot = Join-Path $Workspace 'logs'
$StdoutPath = Join-Path $LogRoot 'controller.stdout.log'
$StderrPath = Join-Path $LogRoot 'controller.stderr.log'
$SupervisorLog = Join-Path $LogRoot 'controller.supervisor.jsonl'
$SelectorCorrectionLauncher = Join-Path $Workspace (
    'diagnostics\pre_freeze_selector_fix_staging\' +
    'h2_prefreeze_selector_correction_bootstrap.py'
)
$RepositoryPython = [IO.Path]::GetFullPath(
    (Join-Path $ToolRoot '..\..\.venv\Scripts\python.exe')
)
if (-not (Test-Path -LiteralPath $RepositoryPython -PathType Leaf)) {
    $RepositoryPython = (Get-Command 'python.exe' -ErrorAction Stop).Source
}
$RecoverablePattern = (
    'PermissionError|WinError 5|Access is denied|sharing violation|' +
    'stale runtime lease has not expired|' +
    'JSONDecodeError:\s+Expecting value:\s+line 1 column 1|' +
    'WorkerStartupError:\s+evaluation-enrollment-' +
    'redimnet2_b2_speaker_embedding-[^:]+:\s+startup timed out after ' +
    '90\.000s;\s+exit_code=None'
)
$DiskReservePattern = (
    'C:\s*free-space reserve is below|' +
    'no new atomic case was started|' +
    'no new paired case was started'
)

if ($TargetFreeGiB -lt $MinimumFreeGiB) {
    throw 'TargetFreeGiB must be greater than or equal to MinimumFreeGiB.'
}

function Get-H2ControllerProcess {
    $WorkspacePattern = [Regex]::Escape($Workspace)
    $DefaultWorkspace = [IO.Path]::GetFullPath(
        (Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17')
    )
    @(
        Get-CimInstance Win32_Process `
            -Filter "Name='python.exe' OR Name='pythonw.exe'" `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $IsDirectController = $_.CommandLine -match (
                    'python(?:\.exe)?"?\s+-m\s+app\.h2_product_program\s+' +
                    '"?(?:Run|Resume)"?(?:\s|$)'
                )
                $IsRetryBootstrap = $_.CommandLine -match (
                    'h2_windows_atomic_retry_bootstrap\.py"?\s+' +
                    '"?(?:Run|Resume)"?(?:\s|$)'
                )
                $IsSelectorCorrection = $_.CommandLine -match (
                    'h2_prefreeze_selector_correction_bootstrap\.py"?\s+' +
                    '"?(?:Run|Resume)"?(?:\s|$)'
                )
                $IsController = (
                    $IsDirectController -or
                    $IsRetryBootstrap -or
                    $IsSelectorCorrection
                )
                $UsesExplicitWorkspace = $_.CommandLine -match '(?:^|\s)--workspace(?:\s|=)'
                $MatchesWorkspace = $_.CommandLine -match $WorkspacePattern
                $UsesDefaultWorkspace = (
                    -not $UsesExplicitWorkspace -and
                    $Workspace.Equals($DefaultWorkspace, [StringComparison]::OrdinalIgnoreCase)
                )
                $IsController -and ($MatchesWorkspace -or $UsesDefaultWorkspace)
            }
    )
}

function Get-H2StorageGuardianProcess {
    $WorkspacePattern = [Regex]::Escape($Workspace)
    @(
        Get-CimInstance Win32_Process `
            -Filter (
                "Name='powershell.exe' OR Name='pwsh.exe' OR " +
                "Name='python.exe' OR Name='pythonw.exe'"
            ) `
            -ErrorAction SilentlyContinue |
            Where-Object {
                $IsGuardian = $_.CommandLine -match (
                    'maintain_h2_storage\.py|run_h2_storage_guardian\.ps1'
                )
                $IsGuardian -and $_.CommandLine -match $WorkspacePattern
            }
    )
}

function Add-H2ProcessArgument {
    param(
        [System.Diagnostics.ProcessStartInfo]$ProcessStartInfo,
        [string]$Value
    )
    if ($ProcessStartInfo.PSObject.Properties.Name -contains 'ArgumentList') {
        [void]$ProcessStartInfo.ArgumentList.Add($Value)
        return
    }
    $Quoted = '"' + [regex]::Replace($Value, '(\\*)"', '$1$1\"') + '"'
    $Quoted = [regex]::Replace($Quoted, '(\\+)"$', '$1$1"')
    $ProcessStartInfo.Arguments = (
        @($ProcessStartInfo.Arguments, $Quoted) |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    ) -join ' '
}

function Get-FileLength {
    param([string]$LiteralPath)
    if (Test-Path -LiteralPath $LiteralPath -PathType Leaf) {
        return (Get-Item -LiteralPath $LiteralPath).Length
    }
    return [int64]0
}

function Get-CDriveFreeGiB {
    $Drive = [IO.DriveInfo]::new('C')
    return [math]::Round($Drive.AvailableFreeSpace / 1GB, 3)
}

function Read-LogDelta {
    param(
        [string]$LiteralPath,
        [int64]$Offset
    )
    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        return ''
    }
    $Bytes = [IO.File]::ReadAllBytes($LiteralPath)
    if ($Offset -ge $Bytes.LongLength) {
        return ''
    }
    $Encoding = if ($Bytes.LongLength -ge 2 -and $Bytes[0] -eq 0xff -and $Bytes[1] -eq 0xfe) {
        [Text.Encoding]::Unicode
    } else {
        [Text.Encoding]::UTF8
    }
    return $Encoding.GetString(
        $Bytes,
        [int]$Offset,
        [int]($Bytes.LongLength - $Offset)
    )
}

function Read-H2JsonSharedDelete {
    param([string]$LiteralPath)
    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        return $null
    }
    $Stream = [IO.File]::Open(
        $LiteralPath,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    )
    try {
        $Reader = [IO.StreamReader]::new($Stream, [Text.Encoding]::UTF8, $true)
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

function Get-H2ProgressIdentity {
    try {
        $Progress = Read-H2JsonSharedDelete -LiteralPath $ProgressPath
        if ($null -eq $Progress) {
            return ''
        }
        return @(
            [string]$Progress.status,
            [string]$Progress.phase,
            [string]$Progress.complete_jobs,
            [string]$Progress.completed_cases,
            [string]$Progress.current_case_id,
            [string]$Progress.updated_at_utc
        ) -join '|'
    }
    catch {
        return ''
    }
}

function Get-H2ProgramStatus {
    try {
        $State = Read-H2JsonSharedDelete -LiteralPath $ProgramStatePath
        if ($null -eq $State) {
            return ''
        }
        return [string]$State.status
    }
    catch {
        return ''
    }
}

function Read-FailedJobDetail {
    if (-not (Test-Path -LiteralPath $ProgramStatePath -PathType Leaf)) {
        return ''
    }
    try {
        $State = Read-H2JsonSharedDelete -LiteralPath $ProgramStatePath
        return @(
            $State.jobs.PSObject.Properties |
                Where-Object { $_.Value.state -eq 'FAILED' } |
                ForEach-Object {
                    # Default interpolation collapses nested arrays to
                    # "System.Object[]". Preserve the complete diagnostic so
                    # recoverable signatures remain detectable even when the
                    # controller stderr log has not received a traceback.
                    $LastError = $_.Value.last_error |
                        ConvertTo-Json -Depth 12 -Compress
                    $LatestActivity = $_.Value.latest_activity |
                        ConvertTo-Json -Depth 12 -Compress
                    "$($_.Name): $LastError $LatestActivity"
                }
        ) -join "`n"
    }
    catch {
        return ''
    }
}

function Write-SupervisorEvent {
    param(
        [string]$Status,
        [string]$Detail
    )
    $Record = [ordered]@{
        schema_version = 'h2-controller-supervisor-event.v1'
        timestamp = [DateTimeOffset]::Now.ToString('o')
        status = $Status
        detail = $Detail
    } | ConvertTo-Json -Compress
    try {
        Add-Content -LiteralPath $SupervisorLog -Value $Record -Encoding UTF8
    }
    catch {
        # Supervisor logging must not turn a recoverable controller exit into a
        # second failure. The visible monitor remains authoritative.
    }
}

function Get-H2SelectorCorrectionArguments {
    param([switch]$PreflightOnly)
    $Arguments = @(
        '-B', $SelectorCorrectionLauncher,
        'Resume',
        '--workspace', $Workspace,
        '--results-root', $ResultsRoot,
        '--summary-root', $SummaryRoot,
        '--config', $Config,
        '--retry-failed'
    )
    if ($PreflightOnly) {
        $Arguments += '--correction-preflight-only'
    }
    return $Arguments
}

function Test-H2SelectorCorrectionEligibility {
    if (
        $DisableSelectorCorrection -or
        -not (Test-Path -LiteralPath $SelectorCorrectionLauncher -PathType Leaf)
    ) {
        return [pscustomobject]@{
            Eligible = $false
            ExitCode = $null
            Detail = 'selector correction is disabled or not staged'
        }
    }

    # PowerShell 5.1 promotes native stderr to NativeCommandError when the
    # script-level error preference is Stop. A fail-closed preflight normally
    # uses stderr with exit code 3, so capture both streams through the process
    # API instead of treating that expected result as a supervisor exception.
    $Info = [System.Diagnostics.ProcessStartInfo]::new()
    $Info.FileName = $RepositoryPython
    $Info.WorkingDirectory = $ToolRoot
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $Info.RedirectStandardOutput = $true
    $Info.RedirectStandardError = $true
    foreach ($Value in @(Get-H2SelectorCorrectionArguments -PreflightOnly)) {
        Add-H2ProcessArgument -ProcessStartInfo $Info -Value $Value
    }
    $Process = [System.Diagnostics.Process]::Start($Info)
    $StdoutTask = $Process.StandardOutput.ReadToEndAsync()
    $StderrTask = $Process.StandardError.ReadToEndAsync()
    $Process.WaitForExit()
    $Stdout = $StdoutTask.Result
    $Stderr = $StderrTask.Result
    $ExitCode = $Process.ExitCode
    $Process.Dispose()
    $Output = @($Stdout, $Stderr) -join [Environment]::NewLine
    return [pscustomobject]@{
        Eligible = $ExitCode -eq 0 -and $Output -match '"status"\s*:\s*"ELIGIBLE"'
        ExitCode = $ExitCode
        Detail = $Output.Trim()
    }
}

function Start-H2SelectorCorrection {
    $Info = [System.Diagnostics.ProcessStartInfo]::new()
    $Info.FileName = $RepositoryPython
    $Info.WorkingDirectory = $ToolRoot
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    foreach ($Value in @(Get-H2SelectorCorrectionArguments)) {
        Add-H2ProcessArgument -ProcessStartInfo $Info -Value $Value
    }
    $Process = [System.Diagnostics.Process]::Start($Info)
    Write-SupervisorEvent -Status 'SELECTOR_CORRECTION_LAUNCHED' -Detail (
        "pid=$($Process.Id); launcher=$SelectorCorrectionLauncher"
    )
    return $Process
}

function Ensure-H2StorageGuardian {
    if ($DisableStorageGuardian -or @(Get-H2StorageGuardianProcess).Count -gt 0) {
        return
    }
    if (-not (Test-Path -LiteralPath $StorageGuardianRunner -PathType Leaf)) {
        Write-SupervisorEvent -Status 'STORAGE_GUARDIAN_MISSING' -Detail $StorageGuardianRunner
        return
    }

    try {
        $Info = [System.Diagnostics.ProcessStartInfo]::new()
        $Info.FileName = (Get-Command 'powershell.exe').Source
        $Info.WorkingDirectory = $ToolRoot
        $Info.UseShellExecute = $false
        $Info.CreateNoWindow = $true
        $Info.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $GuardianArguments = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', $StorageGuardianRunner,
            '-Workspace', $Workspace,
            '-ResultsRoot', $ResultsRoot,
            '-IntervalSeconds', [string]$StorageGuardianIntervalSeconds,
            '-MinimumFreeGiB', [string]$MinimumFreeGiB,
            '-TargetFreeGiB', [string]$TargetFreeGiB
        )
        foreach ($Value in $GuardianArguments) {
            Add-H2ProcessArgument -ProcessStartInfo $Info -Value $Value
        }
        $Process = [System.Diagnostics.Process]::Start($Info)
        Write-SupervisorEvent -Status 'STORAGE_GUARDIAN_LAUNCHED' -Detail (
            "pid=$($Process.Id); interval_seconds=$StorageGuardianIntervalSeconds; " +
            "minimum_free_gib=$MinimumFreeGiB; target_free_gib=$TargetFreeGiB"
        )
    }
    catch {
        Write-SupervisorEvent -Status 'STORAGE_GUARDIAN_LAUNCH_FAILED' -Detail $_.Exception.Message
    }
}

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
if ($SelectorCorrectionPreflightOnly) {
    $Preflight = Test-H2SelectorCorrectionEligibility
    [pscustomobject]@{
        Status = if ($Preflight.Eligible) { 'ELIGIBLE' } else { 'NOT_ELIGIBLE' }
        Eligible = [bool]$Preflight.Eligible
        ExitCode = $Preflight.ExitCode
        Detail = $Preflight.Detail
        ActiveCampaignWasModified = $false
        SelectorCorrectionLauncher = $SelectorCorrectionLauncher
    } | ConvertTo-Json -Depth 8
    exit 0
}
if ($DryRun) {
    [pscustomobject]@{
        Status = 'DRY_RUN_PASS'
        Workspace = $Workspace
        Runner = $Runner
        PollSeconds = $PollSeconds
        LeaseRecoverySeconds = $LeaseRecoverySeconds
        MaximumConsecutiveRecoveries = $MaximumConsecutiveRecoveries
        MaximumUnclassifiedRecoveries = $MaximumUnclassifiedRecoveries
        HealthyProgressResetSeconds = $HealthyProgressResetSeconds
        RecoverablePattern = $RecoverablePattern
        DiskReservePattern = $DiskReservePattern
        ActiveControllerProcesses = @(Get-H2ControllerProcess).Count
        StorageGuardianEnabled = -not $DisableStorageGuardian
        ActiveStorageGuardianProcesses = @(Get-H2StorageGuardianProcess).Count
        StorageGuardianRunner = $StorageGuardianRunner
        StorageGuardianIntervalSeconds = $StorageGuardianIntervalSeconds
        MinimumFreeGiB = $MinimumFreeGiB
        TargetFreeGiB = $TargetFreeGiB
        SelectorCorrectionEnabled = -not $DisableSelectorCorrection
        SelectorCorrectionPreflightOnly = $SelectorCorrectionPreflightOnly.IsPresent
        SelectorCorrectionLauncher = $SelectorCorrectionLauncher
        SelectorCorrectionStaged = Test-Path -LiteralPath `
            $SelectorCorrectionLauncher -PathType Leaf
        SelectorCorrectionPython = $RepositoryPython
    } | ConvertTo-Json
    exit 0
}

$StdoutOffset = Get-FileLength -LiteralPath $StdoutPath
$StderrOffset = Get-FileLength -LiteralPath $StderrPath
$ConsecutiveRecoveries = 0
$UnclassifiedRecoveries = 0
$RecoveryWindowStartedAt = $null
$RecoveryBaselineProgressIdentity = Get-H2ProgressIdentity
Write-SupervisorEvent -Status 'STARTED' -Detail (
    "stdout_offset=$StdoutOffset; stderr_offset=$StderrOffset"
)
Ensure-H2StorageGuardian

while ($true) {
    Ensure-H2StorageGuardian
    if (@(Get-H2ControllerProcess).Count -gt 0) {
        if ($null -ne $RecoveryWindowStartedAt) {
            $CurrentProgressIdentity = Get-H2ProgressIdentity
            $HealthyForSeconds = (
                [DateTimeOffset]::Now - $RecoveryWindowStartedAt
            ).TotalSeconds
            if (
                $HealthyForSeconds -ge $HealthyProgressResetSeconds -and
                -not [string]::IsNullOrWhiteSpace($CurrentProgressIdentity) -and
                $CurrentProgressIdentity -ne $RecoveryBaselineProgressIdentity
            ) {
                $OldRecoveryCount = $ConsecutiveRecoveries
                $OldUnclassifiedCount = $UnclassifiedRecoveries
                $ConsecutiveRecoveries = 0
                $UnclassifiedRecoveries = 0
                $RecoveryWindowStartedAt = $null
                $RecoveryBaselineProgressIdentity = $CurrentProgressIdentity
                Write-SupervisorEvent -Status 'RECOVERY_BUDGET_RESET' -Detail (
                    "healthy scientific progress observed for at least " +
                    "$HealthyProgressResetSeconds seconds; prior_recoveries=" +
                    "$OldRecoveryCount; prior_unclassified=$OldUnclassifiedCount"
                )
            }
        }
        Start-Sleep -Seconds $PollSeconds
        continue
    }

    # Avoid reacting to the brief parent/child handoff used by the launcher.
    Start-Sleep -Seconds 3
    if (@(Get-H2ControllerProcess).Count -gt 0) {
        continue
    }

    $Delta = @(
        Read-LogDelta -LiteralPath $StdoutPath -Offset $StdoutOffset
        Read-LogDelta -LiteralPath $StderrPath -Offset $StderrOffset
        Read-FailedJobDetail
    ) -join "`n"

    # The development selector correction is deliberately external to the
    # prepared runtime identity.  It may take over only after its checksum-bound
    # launcher proves the exact natural Phase-5 failure and unopened held-out
    # boundary.  A non-eligible result falls through to ordinary recovery.
    $SelectorPreflight = Test-H2SelectorCorrectionEligibility
    if ($SelectorPreflight.Eligible) {
        try {
            [void](Start-H2SelectorCorrection)
        }
        catch {
            Write-SupervisorEvent -Status 'SELECTOR_CORRECTION_LAUNCH_FAILED' -Detail (
                $_.Exception.Message
            )
        }
        Start-Sleep -Seconds 5
        continue
    }

    if ($Delta -match $DiskReservePattern) {
        $FreeGiB = Get-CDriveFreeGiB
        Write-SupervisorEvent -Status 'STORAGE_RESERVE_WAIT' -Detail (
            "controller protected C: at $FreeGiB GiB free; waiting for " +
            "$TargetFreeGiB GiB before restart-safe resume"
        )
        while (
            @(Get-H2ControllerProcess).Count -eq 0 -and
            (Get-CDriveFreeGiB) -lt $TargetFreeGiB
        ) {
            Ensure-H2StorageGuardian
            Start-Sleep -Seconds $PollSeconds
        }
        if (@(Get-H2ControllerProcess).Count -gt 0) {
            $StdoutOffset = Get-FileLength -LiteralPath $StdoutPath
            $StderrOffset = Get-FileLength -LiteralPath $StderrPath
            continue
        }

        $FreeGiB = Get-CDriveFreeGiB
        $StdoutOffset = Get-FileLength -LiteralPath $StdoutPath
        $StderrOffset = Get-FileLength -LiteralPath $StderrPath
        try {
            $Launch = & $Runner -Action Resume -RetryFailed -Background `
                -Workspace $Workspace -ResultsRoot $ResultsRoot `
                -SummaryRoot $SummaryRoot -Config $Config | Out-String
            Write-SupervisorEvent -Status 'STORAGE_RESERVE_RELAUNCHED' -Detail (
                "C: recovered to $FreeGiB GiB; $($Launch.Trim())"
            )
        }
        catch {
            Write-SupervisorEvent -Status 'STORAGE_RESERVE_RELAUNCH_FAILED' -Detail (
                "C: free=$FreeGiB GiB; $($_.Exception.Message)"
            )
        }
        Start-Sleep -Seconds 5
        continue
    }

    if ($Delta -notmatch $RecoverablePattern) {
        $StateStatus = Get-H2ProgramStatus
        $IntentionalStop = Test-Path -LiteralPath $StopRequestPath -PathType Leaf
        $TerminalState = (
            $StateStatus -eq 'COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM' -or
            $StateStatus -eq 'STOPPED' -or
            $StateStatus -like 'BLOCKED_*'
        )
        if ($IntentionalStop -or $TerminalState) {
            Write-SupervisorEvent -Status 'STOPPED_INTENTIONAL_OR_TERMINAL' -Detail (
                "program_status=$StateStatus; stop_request_present=$IntentionalStop"
            )
            exit 0
        }
        if (
            $UnclassifiedRecoveries -ge $MaximumUnclassifiedRecoveries -or
            $ConsecutiveRecoveries -ge $MaximumConsecutiveRecoveries
        ) {
            Write-SupervisorEvent -Status 'UNCLASSIFIED_RECOVERY_LIMIT_REACHED' -Detail (
                "program_status=$StateStatus; recovery_count=" +
                "$ConsecutiveRecoveries/$MaximumConsecutiveRecoveries; " +
                "unclassified_count=$UnclassifiedRecoveries/" +
                "$MaximumUnclassifiedRecoveries; no healthy-progress reset; " +
                'stopped for diagnosis'
            )
            exit 0
        }
        $UnclassifiedRecoveries += 1
        $ConsecutiveRecoveries += 1
        Write-SupervisorEvent -Status 'UNCLASSIFIED_RECOVERY_WAIT' -Detail (
            "program_status=$StateStatus; bounded recovery " +
            "$UnclassifiedRecoveries/$MaximumUnclassifiedRecoveries; waiting " +
            "$LeaseRecoverySeconds seconds"
        )
        Start-Sleep -Seconds $LeaseRecoverySeconds
        if (@(Get-H2ControllerProcess).Count -gt 0) {
            $StdoutOffset = Get-FileLength -LiteralPath $StdoutPath
            $StderrOffset = Get-FileLength -LiteralPath $StderrPath
            continue
        }
        $StdoutOffset = Get-FileLength -LiteralPath $StdoutPath
        $StderrOffset = Get-FileLength -LiteralPath $StderrPath
        try {
            $Launch = & $Runner -Action Resume -RetryFailed -Background `
                -Workspace $Workspace -ResultsRoot $ResultsRoot `
                -SummaryRoot $SummaryRoot -Config $Config | Out-String
            $RecoveryWindowStartedAt = [DateTimeOffset]::Now
            $RecoveryBaselineProgressIdentity = Get-H2ProgressIdentity
            Write-SupervisorEvent -Status 'UNCLASSIFIED_RELAUNCHED' -Detail $Launch.Trim()
        }
        catch {
            Write-SupervisorEvent -Status 'UNCLASSIFIED_RELAUNCH_FAILED' -Detail (
                $_.Exception.Message
            )
        }
        Start-Sleep -Seconds 5
        continue
    }

    $ConsecutiveRecoveries += 1
    if ($ConsecutiveRecoveries -gt $MaximumConsecutiveRecoveries) {
        Write-SupervisorEvent -Status 'RECOVERY_LIMIT_REACHED' -Detail (
            "more than $MaximumConsecutiveRecoveries consecutive recoverable " +
            'exits occurred; stopped for diagnosis rather than masking a loop'
        )
        exit 0
    }

    Write-SupervisorEvent -Status 'RECOVERY_WAIT' -Detail (
        "recoverable controller exit detected; waiting $LeaseRecoverySeconds seconds"
    )
    Start-Sleep -Seconds $LeaseRecoverySeconds
    if (@(Get-H2ControllerProcess).Count -gt 0) {
        $StdoutOffset = Get-FileLength -LiteralPath $StdoutPath
        $StderrOffset = Get-FileLength -LiteralPath $StderrPath
        continue
    }

    $StdoutOffset = Get-FileLength -LiteralPath $StdoutPath
    $StderrOffset = Get-FileLength -LiteralPath $StderrPath
    try {
        $Launch = & $Runner -Action Resume -RetryFailed -Background `
            -Workspace $Workspace -ResultsRoot $ResultsRoot `
            -SummaryRoot $SummaryRoot -Config $Config | Out-String
        $RecoveryWindowStartedAt = [DateTimeOffset]::Now
        $RecoveryBaselineProgressIdentity = Get-H2ProgressIdentity
        Write-SupervisorEvent -Status 'RELAUNCHED' -Detail $Launch.Trim()
    }
    catch {
        Write-SupervisorEvent -Status 'RELAUNCH_FAILED' -Detail $_.Exception.Message
    }
    Start-Sleep -Seconds 5
}
