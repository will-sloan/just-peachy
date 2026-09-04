[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$KeepSupersededV16Enabled
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Workspace = Join-Path $ToolRoot 'automated_runs\h2_complete_product_pipeline_v17'
$ResultsRoot = Join-Path $ToolRoot 'JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17'
$SummaryRoot = Join-Path $ToolRoot 'JustPeachyResearchSummaries\h2_complete_product_pipeline_v17'
$PackageRoot = Join-Path $ToolRoot 'JustPeachyResearchSummaries'
$Config = Join-Path $ToolRoot 'configs\automated_evaluation\h2_product_program.v17.yaml'
$PowerShell = (Get-Command 'powershell.exe').Source
$UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$ReceiptPath = Join-Path $Workspace 'storage_maintenance\scheduled_tasks_v17.json'

foreach ($Path in @($Workspace, $ResultsRoot, $PackageRoot)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Required H2 v17 directory is unavailable: $Path"
    }
    if (-not ([IO.Path]::GetFullPath($Path)).StartsWith(
        'C:\', [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "H2 v17 persistence is restricted to C:: $Path"
    }
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "H2 v17 configuration is unavailable: $Config"
}

function ConvertTo-TaskArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value.Contains('"')) {
        throw "Task argument contains an unsupported quote: $Value"
    }
    if ($Value -match '\s') {
        return '"' + $Value + '"'
    }
    return $Value
}

function New-H2TaskDefinition {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string]$Script,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
        throw "Scheduled helper is unavailable: $Script"
    }
    $Tokens = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $Script
    ) + $Arguments
    [pscustomobject]@{
        task_name = $Name
        description = $Description
        executable = $PowerShell
        argument_line = (
            $Tokens | ForEach-Object { ConvertTo-TaskArgument -Value ([string]$_) }
        ) -join ' '
        script = $Script
    }
}

$Definitions = @(
    New-H2TaskDefinition `
        -Name 'JustPeachy H2 v17 Supervisor' `
        -Description 'Restart-safe H2 v17 controller and C-drive storage guardian.' `
        -Script (Join-Path $PSScriptRoot 'supervise_h2_product_program.ps1') `
        -Arguments @(
            '-Workspace', $Workspace,
            '-ResultsRoot', $ResultsRoot,
            '-SummaryRoot', $SummaryRoot,
            '-Config', $Config,
            '-PollSeconds', '20'
        )
    New-H2TaskDefinition `
        -Name 'JustPeachy H2 v17 Milestone Notifier' `
        -Description 'Audible milestone and completion notifications for H2 v17.' `
        -Script (Join-Path $PSScriptRoot 'watch_h2_milestones.ps1') `
        -Arguments @('-Workspace', $Workspace, '-IntervalSeconds', '30')
    New-H2TaskDefinition `
        -Name 'JustPeachy H2 v17 Serial Resource Audit' `
        -Description 'Host-I/O contamination audit for H2 v17 serial resource jobs.' `
        -Script (Join-Path $PSScriptRoot 'watch_h2_serial_resource_io.ps1') `
        -Arguments @(
            '-Workspace', $Workspace,
            '-ResultsRoot', $ResultsRoot,
            '-IntervalSeconds', '60'
        )
    New-H2TaskDefinition `
        -Name 'JustPeachy H2 v17 Post-Campaign Engineering' `
        -Description 'Run the quiet resource replay and UI-latency receipt after H2 v17 completes.' `
        -Script (Join-Path $PSScriptRoot 'watch_h2_postcampaign_engineering.ps1') `
        -Arguments @(
            '-Workspace', $Workspace,
            '-ResultsRoot', $ResultsRoot,
            '-SummaryRoot', $SummaryRoot,
            '-IntervalSeconds', '60',
            '-MinimumFreeGiB', '35',
            '-QuietWindowMinutes', '15',
            '-CooldownSeconds', '60'
        )
    New-H2TaskDefinition `
        -Name 'JustPeachy H2 v17 Final Package Watcher' `
        -Description 'Validate and augment the completed native H2 v17 package.' `
        -Script (Join-Path $PSScriptRoot 'watch_and_augment_h2_final_package.ps1') `
        -Arguments @(
            '-Workspace', $Workspace,
            '-PackageRoot', $PackageRoot,
            '-IntervalSeconds', '60'
        )
)

$SupersededNames = @(
    'JustPeachy H2 v16 Supervisor',
    'JustPeachy H2 v16 Milestone Notifier',
    'JustPeachy H2 v16 Serial Resource Audit',
    'JustPeachy H2 v16 Final Package Watcher'
)

if (-not $Apply) {
    [ordered]@{
        schema_version = 'h2-v17-scheduled-task-registration.v1'
        status = 'PREVIEW'
        applied = $false
        current_user = $UserId
        tasks = $Definitions
        superseded_v16_tasks_would_be_disabled = -not $KeepSupersededV16Enabled
        scientific_configuration_changed = $false
        instruction = 'Rerun with -Apply to register the displayed current-user tasks.'
    } | ConvertTo-Json -Depth 8
    exit 0
}

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $UserId
$Principal = New-ScheduledTaskPrincipal `
    -UserId $UserId -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$Registered = @()
foreach ($Definition in $Definitions) {
    $Action = New-ScheduledTaskAction `
        -Execute $Definition.executable `
        -Argument $Definition.argument_line `
        -WorkingDirectory $ToolRoot
    Register-ScheduledTask `
        -TaskName $Definition.task_name `
        -Description $Definition.description `
        -Action $Action `
        -Trigger $Trigger `
        -Principal $Principal `
        -Settings $Settings `
        -Force | Out-Null
    $Task = Get-ScheduledTask -TaskName $Definition.task_name -ErrorAction Stop
    $ActualArgument = [string]$Task.Actions[0].Arguments
    if (
        $ActualArgument.IndexOf($Workspace, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
        $ActualArgument.IndexOf('h2_complete_product_pipeline_v16', [StringComparison]::OrdinalIgnoreCase) -ge 0
    ) {
        throw "Registered task does not bind the exact v17 workspace: $($Definition.task_name)"
    }
    $Registered += [ordered]@{
        task_name = $Definition.task_name
        state = [string]$Task.State
        executable = [string]$Task.Actions[0].Execute
        arguments = $ActualArgument
    }
}

$Disabled = @()
if (-not $KeepSupersededV16Enabled) {
    foreach ($Name in $SupersededNames) {
        $Task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
        if ($null -eq $Task) {
            continue
        }
        Disable-ScheduledTask -TaskName $Name | Out-Null
        $Disabled += $Name
    }
}

$Receipt = [ordered]@{
    schema_version = 'h2-v17-scheduled-task-registration.v1'
    status = 'APPLIED_AND_VERIFIED'
    applied = $true
    registered_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    current_user = $UserId
    workspace = $Workspace
    results_root = $ResultsRoot
    summary_root = $SummaryRoot
    tasks = $Registered
    superseded_v16_tasks_disabled = $Disabled
    superseded_evidence_deleted = $false
    scientific_configuration_changed = $false
    installer = $MyInvocation.MyCommand.Path
    installer_sha256 = (Get-FileHash -LiteralPath $MyInvocation.MyCommand.Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
$ReceiptDirectory = Split-Path -Parent $ReceiptPath
New-Item -ItemType Directory -Path $ReceiptDirectory -Force | Out-Null
$Temporary = Join-Path $ReceiptDirectory ('.scheduled_tasks_v17.' + [guid]::NewGuid().ToString('N') + '.tmp')
try {
    [IO.File]::WriteAllText(
        $Temporary,
        ($Receipt | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $Temporary -Destination $ReceiptPath -Force
}
finally {
    if (Test-Path -LiteralPath $Temporary -PathType Leaf) {
        Remove-Item -LiteralPath $Temporary -Force -ErrorAction SilentlyContinue
    }
}
$Receipt | ConvertTo-Json -Depth 8
