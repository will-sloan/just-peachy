[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Plan', 'Validate', 'Start', 'RunForeground', 'Status', 'Analyze', 'Collect')]
    [string]$Action = 'Status',
    [string[]]$Backends = @('wespeaker', 'redimnet2_b2_speaker_embedding'),
    [string]$BackendCsv = '',
    [string]$ControllerTag = 'primary',
    [string]$ManagementPython = ''
)

$ErrorActionPreference = 'Stop'
if ($BackendCsv) {
    $Backends = @($BackendCsv.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
if (-not $Backends.Count) { throw 'At least one backend is required.' }
if ($ControllerTag -notmatch '^[A-Za-z0-9_-]+$') { throw 'ControllerTag may contain only letters, digits, underscores, and hyphens.' }
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
$BaseWrapper = Join-Path $PSScriptRoot 'run_speaker_enrollment_study.ps1'
$Config = Join-Path $ToolRoot 'configs\automated_evaluation\speaker_enrollment_live.v2.yaml'
$SourceRoot = Join-Path $ToolRoot 'benchmarks\speaker_breadth\commonvoice_60plus_v1'
$ProtocolRoot = Join-Path $ToolRoot 'benchmarks\speaker_enrollment\speaker_enrollment_live_v2'
$ResultBase = Join-Path $ToolRoot 'JustPeachyResults\speaker_enrollment'
if (-not $ManagementPython) {
    $ManagementPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
}

function Invoke-Management {
    param([string[]]$Arguments)
    & $ManagementPython $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Management command failed with exit code $LASTEXITCODE" }
}

function Get-ProtocolId {
    $Summary = Join-Path $ProtocolRoot 'protocol_summary.json'
    if (-not (Test-Path -LiteralPath $Summary -PathType Leaf)) { throw 'Run -Action Prepare first.' }
    return (Get-Content -LiteralPath $Summary -Raw | ConvertFrom-Json).protocol_id
}

function Get-RunRoot {
    return Join-Path $ResultBase (Get-ProtocolId)
}

function Get-ControllerRoot {
    $Name = if ($ControllerTag -eq 'primary') { '_controller' } else { "_controller_$ControllerTag" }
    return Join-Path (Get-RunRoot) $Name
}

function Write-State {
    param([string]$Stage, [string]$Detail, [string]$Status = 'RUNNING')
    $Root = Get-ControllerRoot
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    [ordered]@{
        schema_version = 'speaker-enrollment-live-controller.v2'
        status = $Status
        stage = $Stage
        detail = $Detail
        updated_at = (Get-Date).ToString('o')
        protocol_id = Get-ProtocolId
        controller_tag = $ControllerTag
        backends = $Backends
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Root 'state.json') -Encoding UTF8
}

function Invoke-Base {
    param([string]$BaseAction, [string]$Phase = 'All', [string[]]$SelectedBackends = $Backends, [string]$Reference = '')
    if ($ControllerTag -eq 'primary') {
        & $BaseWrapper -Action $BaseAction -Phase $Phase -SourceProtocolRoot $SourceRoot `
            -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -ManagementPython $ManagementPython `
            -Backends $SelectedBackends -ReferenceEnrollmentConfigId $Reference
    }
    else {
        $AnalysisRoot = Join-Path (Get-RunRoot) "analysis_$ControllerTag"
        $CollectRoot = Join-Path $ToolRoot "JustPeachyResearchSummaries\speaker_enrollment_live_v2_$(Get-ProtocolId)_$ControllerTag"
        & $BaseWrapper -Action $BaseAction -Phase $Phase -SourceProtocolRoot $SourceRoot `
            -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -ManagementPython $ManagementPython `
            -Backends $SelectedBackends -ReferenceEnrollmentConfigId $Reference `
            -AnalysisRoot $AnalysisRoot -CollectRoot $CollectRoot
    }
    if ($LASTEXITCODE -ne 0) { throw "$BaseAction/$Phase failed with exit code $LASTEXITCODE" }
}

function Start-LoggedProcess {
    param([string]$FilePath, [string[]]$Arguments, [string]$Name)
    $Root = Get-ControllerRoot
    $Stdout = Join-Path $Root "$Name.stdout.log"
    $Stderr = Join-Path $Root "$Name.stderr.log"
    $Quoted = foreach ($Value in $Arguments) {
        if ($Value -match '[\s"]') { '"' + ($Value -replace '"', '\"') + '"' } else { $Value }
    }
    $Process = Start-Process -FilePath $FilePath -ArgumentList $Quoted -WorkingDirectory $ToolRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    # Windows PowerShell can return a blank ExitCode if the native process exits
    # before its handle is retained. Opening the handle now makes later exit-code
    # reads reliable while preserving parallel execution and redirected logs.
    $null = $Process.Handle
    return $Process
}

function Preserve-PreviousControllerAttempt {
    $Root = Get-ControllerRoot
    $Existing = @(
        Get-ChildItem -LiteralPath $Root -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '*.log' -or $_.Name -in @('state.json', 'controller.pid') }
    )
    if (-not $Existing.Count) { return }
    $AttemptRoot = Join-Path $Root ("attempts\{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $AttemptRoot | Out-Null
    foreach ($Item in $Existing) {
        Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $AttemptRoot $Item.Name)
    }
}

function Run-Extraction {
    $RunRoot = Get-RunRoot
    $Controller = Get-ControllerRoot
    $SliceList = Join-Path $Controller 'all_required_slices.txt'
    $AllSliceIds = @(
        Import-Csv -LiteralPath (Join-Path $ProtocolRoot 'audio_slices.tsv') -Delimiter "`t" |
        Select-Object -ExpandProperty slice_id |
        Sort-Object -Unique
    )
    $AllSliceIds | Set-Content -LiteralPath $SliceList -Encoding ASCII
    $ProcessRows = @()
    foreach ($Backend in $Backends) {
        $CacheRoot = Join-Path (Join-Path $RunRoot $Backend) 'embeddings'
        $ExistingSummaryPath = Join-Path $CacheRoot 'cache_summary.json'
        if (Test-Path -LiteralPath $ExistingSummaryPath -PathType Leaf) {
            $ExistingSummary = Get-Content -LiteralPath $ExistingSummaryPath -Raw | ConvertFrom-Json
            $StatusTotal = ($ExistingSummary.statuses.psobject.Properties | ForEach-Object { [int]$_.Value } | Measure-Object -Sum).Sum
            if (
                $ExistingSummary.protocol_id -eq (Get-ProtocolId) -and
                $ExistingSummary.backend_id -eq $Backend -and
                [int]$ExistingSummary.cached_items_in_requested_scope -eq $AllSliceIds.Count -and
                [int]$StatusTotal -eq $AllSliceIds.Count -and
                (Test-Path -LiteralPath (Join-Path $CacheRoot 'backend_identity.json') -PathType Leaf)
            ) {
                Write-Output "[REUSE COMPLETE CACHE] $Backend $($AllSliceIds.Count) slices"
                continue
            }
        }
        $RuntimeText = & $ManagementPython $Launcher speaker-enrollment backend-runtime --backend $Backend
        if ($LASTEXITCODE -ne 0) { throw "Runtime resolution failed for $Backend" }
        $Runtime = $RuntimeText | Out-String | ConvertFrom-Json
        $Arguments = @(
            '-m', 'app.speaker_enrollment.worker',
            '--protocol-root', $ProtocolRoot,
            '--component', $Backend,
            '--cache-root', $CacheRoot,
            '--slice-list', $SliceList
        )
        $ProcessRows += [pscustomobject]@{
            Backend = $Backend
            Process = Start-LoggedProcess -FilePath $Runtime.python -Arguments $Arguments -Name "extract_$Backend"
            PeakWorkingSetBytes = 0
        }
    }
    while ($ProcessRows | Where-Object { -not $_.Process.HasExited }) {
        foreach ($Row in $ProcessRows) {
            if (-not $Row.Process.HasExited) {
                $Row.Process.Refresh()
                $Row.PeakWorkingSetBytes = [Math]::Max([int64]$Row.PeakWorkingSetBytes, [int64]$Row.Process.PeakWorkingSet64)
            }
        }
        Start-Sleep -Seconds 2
    }
    foreach ($Row in $ProcessRows) {
        $Process = $Row.Process
        $Process.WaitForExit()
        $Process.Refresh()
        $ExitCode = $Process.ExitCode
        if ($null -ne $ExitCode -and $ExitCode -ne 0) {
            throw "Embedding extraction process $($Process.Id) failed with exit code $ExitCode"
        }
    }
    $Telemetry = @()
    foreach ($Backend in $Backends) {
        $ProcessRow = $ProcessRows | Where-Object { $_.Backend -eq $Backend } | Select-Object -First 1
        $CacheSummaryPath = Join-Path (Join-Path (Join-Path $RunRoot $Backend) 'embeddings') 'cache_summary.json'
        $CacheSummary = Get-Content -LiteralPath $CacheSummaryPath -Raw | ConvertFrom-Json
        $CacheStatusTotal = ($CacheSummary.statuses.psobject.Properties | ForEach-Object { [int]$_.Value } | Measure-Object -Sum).Sum
        $UnexpectedCacheStatuses = @(
            $CacheSummary.statuses.psobject.Properties |
            Where-Object { $_.Name -notin @('ok', 'too_short') -and [int]$_.Value -gt 0 }
        )
        if (
            $CacheSummary.protocol_id -ne (Get-ProtocolId) -or
            $CacheSummary.backend_id -ne $Backend -or
            [int]$CacheSummary.cached_items_in_requested_scope -ne $AllSliceIds.Count -or
            [int]$CacheStatusTotal -ne $AllSliceIds.Count -or
            $UnexpectedCacheStatuses.Count -gt 0
        ) {
            throw "Embedding cache completion validation failed for $Backend."
        }
        switch ($Backend) {
            'wespeaker' {
                $ModelPath = Join-Path $RepoRoot 'models\cache\wespeaker\english'
                $ModelBytes = (Get-ChildItem -LiteralPath $ModelPath -File -Recurse | Measure-Object -Property Length -Sum).Sum
                $ModelBytesDefinition = 'all files in pinned active WeSpeaker model directory'
            }
            'redimnet2_b2_speaker_embedding' {
                $ModelPath = Join-Path $RepoRoot 'models\cache\redimnet2\b2-vox2-lm.pt'
                $ModelBytes = (Get-Item -LiteralPath $ModelPath).Length
                $ModelBytesDefinition = 'pinned active ReDimNet2-B2 checkpoint file'
            }
            'speechbrain_ecapa' {
                $ModelPath = Join-Path $RepoRoot 'models\cache\speechbrain\spkrec-ecapa-voxceleb'
                $ModelBytes = (Get-ChildItem -LiteralPath $ModelPath -File -Recurse | Measure-Object -Property Length -Sum).Sum
                $ModelBytesDefinition = 'all files in pinned active SpeechBrain ECAPA model directory'
            }
            'eres2net_base_speaker_embedding' {
                $ModelPath = Join-Path $RepoRoot 'models\cache\sherpa_onnx\speaker_embedding\3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx'
                $ModelBytes = (Get-Item -LiteralPath $ModelPath).Length
                $ModelBytesDefinition = 'pinned active ERes2Net Base ONNX model file'
            }
            default { throw "Runtime telemetry has no model-artifact mapping for $Backend." }
        }
        $Telemetry += [ordered]@{
            backend = $Backend
            peak_process_working_set_bytes = if ($ProcessRow) { [int64]$ProcessRow.PeakWorkingSetBytes } else { $null }
            peak_process_working_set_scope = if ($ProcessRow) { 'complete extraction worker process' } else { 'unavailable: resumed from a complete cache after an orchestration-only failure' }
            model_artifact_bytes = [int64]$ModelBytes
            model_artifact_definition = $ModelBytesDefinition
            model_artifact_path = $ModelPath
            successful_audio_duration_sec = $CacheSummary.successful_audio_duration_sec_in_requested_scope
            extraction_sec_sum = $CacheSummary.total_extraction_sec_in_requested_scope
            embedding_realtime_factor = $CacheSummary.embedding_realtime_factor
            timing_semantics = 'sum of per-slice embed calls; two backends ran concurrently'
        }
    }
    [ordered]@{
        schema_version = 'speaker-enrollment-runtime-telemetry.v2'
        protocol_id = Get-ProtocolId
        controller_tag = $ControllerTag
        matched_cpu_run = $true
        backends_ran_concurrently = $true
        rows = $Telemetry
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Controller 'runtime_telemetry.json') -Encoding UTF8
}

function Run-PhaseParallel {
    param([string]$Phase, [string]$Reference = '')
    $Processes = @()
    foreach ($Backend in $Backends) {
        $Arguments = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $BaseWrapper,
            '-Action', 'Run', '-Phase', $Phase,
            '-SourceProtocolRoot', $SourceRoot, '-ProtocolRoot', $ProtocolRoot,
            '-ResultBase', $ResultBase, '-ManagementPython', $ManagementPython,
            '-Backends', $Backend
        )
        if ($Reference) { $Arguments += @('-ReferenceEnrollmentConfigId', $Reference) }
        $Processes += Start-LoggedProcess -FilePath 'powershell.exe' -Arguments $Arguments -Name "phase_${Phase}_$Backend"
    }
    foreach ($Process in $Processes) {
        $Process.WaitForExit()
        $Process.Refresh()
        $ExitCode = $Process.ExitCode
        if ($ExitCode -ne 0) { throw "$Phase process $($Process.Id) failed with exit code $ExitCode" }
    }
}

function Run-AutomaticPhaseE {
    $RunRoot = Get-RunRoot
    $Processes = @()
    foreach ($Backend in $Backends) {
        $Gate = Join-Path (Get-ControllerRoot) "automatic_phase_e_gate_$Backend.yaml"
        Invoke-Management @(
            'speaker-enrollment', 'auto-gate',
            '--protocol-root', $ProtocolRoot,
            '--result-base', $RunRoot,
            '--backend', $Backend,
            '--output', $Gate,
            '--enrollment-configurations', '2'
        )
        $Arguments = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $BaseWrapper,
            '-Action', 'Run', '-Phase', 'JointFrontier',
            '-SourceProtocolRoot', $SourceRoot, '-ProtocolRoot', $ProtocolRoot,
            '-ResultBase', $ResultBase, '-ManagementPython', $ManagementPython,
            '-Backends', $Backend, '-DecisionGate', $Gate
        )
        $Processes += Start-LoggedProcess -FilePath 'powershell.exe' -Arguments $Arguments -Name "phase_JointFrontier_$Backend"
    }
    foreach ($Process in $Processes) {
        $Process.WaitForExit()
        $Process.Refresh()
        $ExitCode = $Process.ExitCode
        if ($ExitCode -ne 0) { throw "JointFrontier process $($Process.Id) failed with exit code $ExitCode" }
    }
}

function Format-ProgressBar {
    param([double]$Fraction, [int]$Width = 24)
    $Bounded = [Math]::Max(0.0, [Math]::Min(1.0, $Fraction))
    $Filled = [int][Math]::Floor($Bounded * $Width)
    return ('[' + ('#' * $Filled) + ('-' * ($Width - $Filled)) + ']')
}

function Run-Study {
    $ProtocolSummary = Join-Path $ProtocolRoot 'protocol_summary.json'
    if (-not (Test-Path -LiteralPath $ProtocolSummary -PathType Leaf)) {
        Invoke-Management @('speaker-enrollment', 'prepare', '--config', $Config, '--source-protocol-root', $SourceRoot, '--protocol-root', $ProtocolRoot)
    }
    else {
        Write-Output "Reusing frozen protocol $((Get-Content -LiteralPath $ProtocolSummary -Raw | ConvertFrom-Json).protocol_id)."
    }
    Invoke-Base -BaseAction Validate
    Write-State -Stage 'EXTRACTION' -Detail 'Embedding every immutable slice once per finalist in parallel.'
    Run-Extraction
    foreach ($Phase in @('EnrollmentCount', 'EnrollmentDuration', 'Aggregation')) {
        Write-State -Stage $Phase -Detail "Evaluating $Phase for both finalists in parallel."
        Run-PhaseParallel -Phase $Phase
    }
    $Reference = Import-Csv -LiteralPath (Join-Path $ProtocolRoot 'configurations.tsv') -Delimiter "`t" |
        Where-Object {
            $_.phase -eq 'EnrollmentCount' -and $_.enrollment_count -eq '5' -and
            $_.repetition -eq '0' -and $_.aggregation_method -eq 'normalized_mean'
        } |
        Select-Object -First 1 -ExpandProperty configuration_id
    if (-not $Reference) { throw 'Could not resolve the frozen five-utterance reference configuration.' }
    Write-State -Stage 'ProbeDuration' -Detail "Running causal nested-prefix study with reference $Reference."
    Run-PhaseParallel -Phase ProbeDuration -Reference $Reference
    Write-State -Stage 'JointFrontier' -Detail 'Generating calibration-only gates and running automatic Phase E.'
    Run-AutomaticPhaseE
    Write-State -Stage 'Analyze' -Detail 'Building speaker-bootstrap, hubness, quality, and causal reports.'
    Invoke-Base -BaseAction Analyze
    Write-State -Stage 'Collect' -Detail 'Exporting the compact reproducibility and analysis package.'
    Invoke-Base -BaseAction Collect
    Write-State -Stage 'Complete' -Detail 'Phases A-E, analysis, and compact export are complete; the automatic Phase-E gate used calibration evidence only.' -Status 'COMPLETE'
}

switch ($Action) {
    'Prepare' {
        Invoke-Management @('speaker-enrollment', 'prepare', '--config', $Config, '--source-protocol-root', $SourceRoot, '--protocol-root', $ProtocolRoot)
    }
    'Plan' { Invoke-Base -BaseAction Plan }
    'Validate' { Invoke-Base -BaseAction Validate }
    'RunForeground' {
        try { Run-Study } catch { Write-State -Stage 'Failed' -Detail $_.Exception.Message -Status 'FAILED'; throw }
    }
    'Start' {
        if (-not (Test-Path -LiteralPath (Join-Path $ProtocolRoot 'protocol_summary.json'))) {
            Invoke-Management @('speaker-enrollment', 'prepare', '--config', $Config, '--source-protocol-root', $SourceRoot, '--protocol-root', $ProtocolRoot)
        }
        $Controller = Get-ControllerRoot
        New-Item -ItemType Directory -Force -Path $Controller | Out-Null
        $PidFile = Join-Path $Controller 'controller.pid'
        if (Test-Path -LiteralPath $PidFile) {
            $ExistingPid = [int](Get-Content -LiteralPath $PidFile -Raw)
            if (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue) { throw "The study is already running as PID $ExistingPid." }
        }
        Preserve-PreviousControllerAttempt
        $Arguments = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath,
            '-Action', 'RunForeground', '-ControllerTag', $ControllerTag,
            '-BackendCsv', ($Backends -join ',')
        )
        Write-State -Stage 'Starting' -Detail 'Launching the background controller.'
        $Process = Start-LoggedProcess -FilePath 'powershell.exe' -Arguments $Arguments -Name 'controller'
        $Process.Id | Set-Content -LiteralPath $PidFile -Encoding ASCII
        [ordered]@{ status = 'STARTED'; pid = $Process.Id; protocol_id = Get-ProtocolId; controller_tag = $ControllerTag; backends = $Backends; controller_root = $Controller } | ConvertTo-Json
    }
    'Status' {
        $Root = Get-ControllerRoot
        if (Test-Path -LiteralPath (Join-Path $Root 'state.json')) { Get-Content -LiteralPath (Join-Path $Root 'state.json') -Raw }
        Invoke-Base -BaseAction Status
        foreach ($Backend in $Backends) {
            $Items = Join-Path (Join-Path (Get-RunRoot) $Backend) 'embeddings\items'
            $Count = if (Test-Path -LiteralPath $Items) { (Get-ChildItem -LiteralPath $Items -Filter '*.npz' -File).Count } else { 0 }
            $CacheFraction = $Count / 20574.0
            $CompletedConfigurations = 0
            foreach ($PhaseDirectory in @(
                'phase_a_enrollment_count', 'phase_b_enrollment_duration', 'phase_c_aggregation',
                'phase_d_probe_duration', 'phase_e_joint_frontier'
            )) {
                $PhaseRoot = Join-Path (Join-Path (Get-RunRoot) $Backend) $PhaseDirectory
                if (Test-Path -LiteralPath $PhaseRoot) {
                    $CompletedConfigurations += @(
                        Get-ChildItem -LiteralPath $PhaseRoot -Directory |
                        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'configuration_result.json') }
                    ).Count
                }
            }
            $ExpectedConfigurations = 156
            $EvaluationFraction = $CompletedConfigurations / [double]$ExpectedConfigurations
            $OverallFraction = 0.20 * $CacheFraction + 0.80 * $EvaluationFraction
            Write-Output ("EXTRACTION {0} {1,6:N2}%  {2}/20574  {3}" -f $Backend, (100*$CacheFraction), $Count, (Format-ProgressBar $CacheFraction))
            Write-Output ("EVALUATION {0} {1,6:N2}%  {2}/{3} configs  {4}" -f $Backend, (100*$EvaluationFraction), $CompletedConfigurations, $ExpectedConfigurations, (Format-ProgressBar $EvaluationFraction))
            Write-Output ("OVERALL    {0} {1,6:N2}%  {2}" -f $Backend, (100*$OverallFraction), (Format-ProgressBar $OverallFraction))
        }
    }
    'Analyze' { Invoke-Base -BaseAction Analyze }
    'Collect' { Invoke-Base -BaseAction Collect }
}
