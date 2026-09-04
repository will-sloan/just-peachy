[CmdletBinding()]
param(
    [ValidateSet('Audit','Prepare','Validate','Plan','Smoke','Run','Resume','Status','Stop','Analyze','Collect','ExportPortable','LaunchDemo')]
    [string]$Action = 'Status',
    [string]$Workspace,
    [string]$ResultsRoot,
    [string]$SummaryRoot,
    [string]$Config,
    [ValidateRange(1,1000000)]
    [int]$MaximumJobs,
    [switch]$RetryFailed,
    [switch]$Background,
    [switch]$OpenMonitor,
    [switch]$DryRun,
    [string]$StopReason = 'operator_requested'
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Project Python is unavailable: $Python"
}
$RetryBootstrap = Join-Path $PSScriptRoot 'h2_windows_atomic_retry_bootstrap.py'
if (-not (Test-Path -LiteralPath $RetryBootstrap -PathType Leaf)) {
    throw "H2 Windows atomic-publication bootstrap is unavailable: $RetryBootstrap"
}

# Resolve operator overrides before changing the working directory. This keeps
# relative paths stable and makes paths containing spaces safe in child
# processes and in the monitor.
if (-not [string]::IsNullOrWhiteSpace($Workspace)) { $Workspace = [IO.Path]::GetFullPath($Workspace) }
if (-not [string]::IsNullOrWhiteSpace($ResultsRoot)) { $ResultsRoot = [IO.Path]::GetFullPath($ResultsRoot) }
if (-not [string]::IsNullOrWhiteSpace($SummaryRoot)) { $SummaryRoot = [IO.Path]::GetFullPath($SummaryRoot) }
if (-not [string]::IsNullOrWhiteSpace($Config)) { $Config = [IO.Path]::GetFullPath($Config) }
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
if ($DryRun -and $Action -ne 'LaunchDemo') {
    throw '-DryRun is supported only with -Action LaunchDemo.'
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
    # Windows PowerShell 5.1 fallback. Escape every quote and the run of
    # backslashes that precedes it according to CommandLineToArgvW rules.
    $Quoted = '"' + [regex]::Replace($Value, '(\\*)"', '$1$1\"') + '"'
    $Quoted = [regex]::Replace($Quoted, '(\\+)"$', '$1$1"')
    $ProcessStartInfo.Arguments = (
        @($ProcessStartInfo.Arguments, $Quoted) |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    ) -join ' '
}

$Arguments = @($RetryBootstrap, $Action)
if (-not [string]::IsNullOrWhiteSpace($Workspace)) { $Arguments += @('--workspace', $Workspace) }
if (-not [string]::IsNullOrWhiteSpace($ResultsRoot)) { $Arguments += @('--results-root', $ResultsRoot) }
if (-not [string]::IsNullOrWhiteSpace($SummaryRoot)) { $Arguments += @('--summary-root', $SummaryRoot) }
if (-not [string]::IsNullOrWhiteSpace($Config)) { $Arguments += @('--config', $Config) }
if ($PSBoundParameters.ContainsKey('MaximumJobs')) { $Arguments += @('--maximum-jobs', [string]$MaximumJobs) }
if ($RetryFailed) { $Arguments += '--retry-failed' }
if ($DryRun) { $Arguments += '--dry-run' }
if ($Action -eq 'Stop') { $Arguments += @('--reason', $StopReason) }

# Keep Audit/Validate/Plan/Status and the supported demo dry run genuinely
# read-only. The retry shim can protect os.replace without a receipt path;
# durable policy/event artifacts are installed only for actions that may
# publish campaign state. Removing inherited values also makes this true when
# the wrapper is launched from a shell that previously ran a mutating action.
$AtomicPublicationActions = @(
    'Prepare','Smoke','Run','Resume','Stop','Analyze','Collect','ExportPortable','LaunchDemo'
)
$InstallAtomicPublicationEvidence = (-not $DryRun) -and ($Action -in $AtomicPublicationActions)
if ($InstallAtomicPublicationEvidence) {
    $env:H2_ATOMIC_RETRY_POLICY_ROOT = Join-Path $Workspace 'storage_maintenance'
    $env:H2_ATOMIC_RETRY_EVENT_LOG = Join-Path $Workspace 'logs\windows_atomic_publication_events.jsonl'
} else {
    Remove-Item Env:H2_ATOMIC_RETRY_POLICY_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:H2_ATOMIC_RETRY_EVENT_LOG -ErrorAction SilentlyContinue
}

function Open-H2Monitor {
    $MonitorScript = Join-Path $PSScriptRoot 'monitor_h2_product_program.ps1'
    $MonitorArguments = @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $MonitorScript, '-Follow', '-IntervalSeconds', '30')
    if (-not [string]::IsNullOrWhiteSpace($Workspace)) {
        $MonitorArguments += @('-Workspace', $Workspace)
    }
    if (-not [string]::IsNullOrWhiteSpace($ResultsRoot)) {
        $MonitorArguments += @('-ResultsRoot', $ResultsRoot)
    }
    if (-not [string]::IsNullOrWhiteSpace($SummaryRoot)) {
        $MonitorArguments += @('-SummaryRoot', $SummaryRoot)
    }
    if (-not [string]::IsNullOrWhiteSpace($Config)) {
        $MonitorArguments += @('-Config', $Config)
    }
    $MonitorInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $MonitorInfo.FileName = (Get-Command 'powershell.exe').Source
    $MonitorInfo.WorkingDirectory = $ToolRoot
    $MonitorInfo.UseShellExecute = $true
    $MonitorInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Normal
    foreach ($Value in $MonitorArguments) {
        Add-H2ProcessArgument -ProcessStartInfo $MonitorInfo -Value $Value
    }
    [void][System.Diagnostics.Process]::Start($MonitorInfo)
}

function Ensure-H2FinalPackageWatcher {
    $WatcherScript = Join-Path $PSScriptRoot 'watch_and_augment_h2_final_package.ps1'
    if (-not (Test-Path -LiteralPath $WatcherScript -PathType Leaf)) {
        throw "H2 final-package watcher is unavailable: $WatcherScript"
    }
    $PackageRoot = [IO.Path]::GetDirectoryName($SummaryRoot.TrimEnd('\'))
    if ([string]::IsNullOrWhiteSpace($PackageRoot)) {
        throw "Cannot derive the H2 package root from summary root: $SummaryRoot"
    }
    foreach ($Directory in @($Workspace, $PackageRoot)) {
        if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
            New-Item -ItemType Directory -Path $Directory -Force | Out-Null
        }
    }
    $Existing = @(
        Get-CimInstance Win32_Process `
            -Filter "Name='powershell.exe' OR Name='pwsh.exe'" `
            -ErrorAction Stop |
            Where-Object {
                $_.Name -in @('powershell.exe', 'pwsh.exe') -and
                -not [string]::IsNullOrWhiteSpace([string]$_.CommandLine) -and
                ([string]$_.CommandLine).IndexOf(
                    $WatcherScript,
                    [StringComparison]::OrdinalIgnoreCase
                ) -ge 0 -and
                ([string]$_.CommandLine).IndexOf(
                    $Workspace,
                    [StringComparison]::OrdinalIgnoreCase
                ) -ge 0
            }
    )
    if ($Existing.Count -gt 0) {
        return [pscustomobject]@{
            Pid = [int]$Existing[0].ProcessId
            Reused = $true
            PackageRoot = $PackageRoot
            WorkspacePointer = Join-Path $Workspace 'final_augmented_collection.json'
            PackagePointer = Join-Path $PackageRoot 'LATEST_H2_AUGMENTED_PACKAGE.json'
        }
    }
    $WatcherInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $WatcherInfo.FileName = (Get-Command 'powershell.exe').Source
    $WatcherInfo.WorkingDirectory = $ToolRoot
    $WatcherInfo.UseShellExecute = $false
    $WatcherInfo.CreateNoWindow = $true
    $WatcherInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $WatcherArguments = @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $WatcherScript,
        '-Workspace',
        $Workspace,
        '-PackageRoot',
        $PackageRoot,
        '-IntervalSeconds',
        '60'
    )
    foreach ($Value in $WatcherArguments) {
        Add-H2ProcessArgument -ProcessStartInfo $WatcherInfo -Value $Value
    }
    $WatcherProcess = [System.Diagnostics.Process]::Start($WatcherInfo)
    return [pscustomobject]@{
        Pid = $WatcherProcess.Id
        Reused = $false
        PackageRoot = $PackageRoot
        WorkspacePointer = Join-Path $Workspace 'final_augmented_collection.json'
        PackagePointer = Join-Path $PackageRoot 'LATEST_H2_AUGMENTED_PACKAGE.json'
    }
}

$FinalPackageWatcher = $null
if ($Action -in @('Run','Resume') -and -not $DryRun) {
    $FinalPackageWatcher = Ensure-H2FinalPackageWatcher
}

Push-Location $ToolRoot
try {
    if ($Background) {
        if ($Action -notin @('Run','Resume')) {
            throw '-Background is supported only with -Action Run or Resume.'
        }
        $ResolvedWorkspace = if ([string]::IsNullOrWhiteSpace($Workspace)) {
            Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
        } else {
            $Workspace
        }
        $LogRoot = Join-Path $ResolvedWorkspace 'logs'
        New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
        $Stdout = Join-Path $LogRoot 'controller.stdout.log'
        $Stderr = Join-Path $LogRoot 'controller.stderr.log'
        # A fixed child command reads every variable argument from JSON-backed
        # environment values. No path is interpolated into a command string.
        $BackgroundInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $BackgroundInfo.FileName = (Get-Command 'powershell.exe').Source
        $BackgroundInfo.WorkingDirectory = $ToolRoot
        $BackgroundInfo.UseShellExecute = $false
        $BackgroundInfo.CreateNoWindow = $true
        $BackgroundInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $BackgroundInfo.EnvironmentVariables['H2_BACKGROUND_PYTHON'] = $Python
        $BackgroundInfo.EnvironmentVariables['H2_BACKGROUND_ARGUMENTS_JSON'] = ($Arguments | ConvertTo-Json -Compress)
        $BackgroundInfo.EnvironmentVariables['H2_BACKGROUND_STDOUT'] = $Stdout
        $BackgroundInfo.EnvironmentVariables['H2_BACKGROUND_STDERR'] = $Stderr
        $BackgroundInfo.EnvironmentVariables['H2_ATOMIC_RETRY_POLICY_ROOT'] = $env:H2_ATOMIC_RETRY_POLICY_ROOT
        $BackgroundInfo.EnvironmentVariables['H2_ATOMIC_RETRY_EVENT_LOG'] = $env:H2_ATOMIC_RETRY_EVENT_LOG
        $ChildCommand = '$a=@(ConvertFrom-Json -InputObject $env:H2_BACKGROUND_ARGUMENTS_JSON); & $env:H2_BACKGROUND_PYTHON @a 1>> $env:H2_BACKGROUND_STDOUT 2>> $env:H2_BACKGROUND_STDERR; exit $LASTEXITCODE'
        foreach ($Value in @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $ChildCommand)) {
            Add-H2ProcessArgument -ProcessStartInfo $BackgroundInfo -Value $Value
        }
        $Process = [System.Diagnostics.Process]::Start($BackgroundInfo)
        if ($OpenMonitor) { Open-H2Monitor }
        [pscustomobject]@{
            Status = 'LAUNCHED'
            Pid = $Process.Id
            Stdout = $Stdout
            Stderr = $Stderr
            MonitorCommand = ".\scripts\monitor_h2_product_program.ps1 -Follow -IntervalSeconds 30"
            FinalPackageWatcherPid = $FinalPackageWatcher.Pid
            FinalPackageWatcherReused = $FinalPackageWatcher.Reused
            FinalPackageWorkspacePointer = $FinalPackageWatcher.WorkspacePointer
            FinalPackageRootPointer = $FinalPackageWatcher.PackagePointer
        } | ConvertTo-Json
        exit 0
    }
    if ($OpenMonitor) {
        if ($Action -notin @('Run','Resume')) {
            throw '-OpenMonitor is supported only with -Action Run or Resume.'
        }
        Open-H2Monitor
    }
    & $Python @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
