[CmdletBinding()]
param(
    [switch]$Follow,
    [ValidateRange(2,3600)]
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ProgressPath = Join-Path $ToolRoot 'JustPeachyResults\diarization_product_v2_development\campaign_progress.json'
$StatePath = Join-Path $ToolRoot 'JustPeachyResults\diarization_product_v2_development\controller_state.json'
$ResultRoot = Join-Path $ToolRoot 'JustPeachyResults\diarization_product_v2_development'
$CaseIndex = @{}
foreach ($manifest in @(
    (Join-Path $ToolRoot 'benchmarks\stage11\controlled_diarization_v1\development\case_manifest.jsonl'),
    (Join-Path $ToolRoot 'benchmarks\stage11\diarization_product_v2\development\case_manifest.jsonl')
)) {
    if (Test-Path -LiteralPath $manifest -PathType Leaf) {
        foreach ($line in Get-Content -LiteralPath $manifest) {
            if ($line.Trim()) {
                $case = $line | ConvertFrom-Json
                $CaseIndex[[string]$case.case_id] = $case
            }
        }
    }
}

function Format-Duration([Nullable[double]]$Seconds) {
    if ($null -eq $Seconds) { return 'calculating' }
    return [TimeSpan]::FromSeconds([Math]::Max(0, $Seconds)).ToString('hh\:mm\:ss')
}

function Format-Bar([double]$Percent, [int]$Width = 28) {
    $bounded = [Math]::Max(0, [Math]::Min(100, $Percent))
    $filled = [int][Math]::Round($bounded * $Width / 100)
    return '[' + ('#' * $filled) + ('-' * ($Width - $filled)) + ('] {0,6:N1}%' -f $bounded)
}

function Show-Progress {
    Clear-Host
    Write-Host 'JUST-PEACHY DIARIZATION DEVELOPMENT'
    Write-Host ''
    if (-not (Test-Path -LiteralPath $ProgressPath -PathType Leaf)) {
        Write-Host "Progress has not started: $ProgressPath"
        return
    }
    try {
        $progress = Get-Content -LiteralPath $ProgressPath -Raw | ConvertFrom-Json
    }
    catch {
        Write-Host 'Progress sidecar is between atomic refreshes; retrying.'
        return
    }
    $state = $null
    if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
        try { $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json } catch { }
    }
    Write-Host 'Overall'
    Write-Host (Format-Bar ([double]$progress.overall_audio_weighted_percentage))
    Write-Host ('Units:   {0:N1}%' -f [double]$progress.overall_unit_percentage)
    Write-Host ('Elapsed: {0}' -f (Format-Duration ([double]$progress.elapsed_seconds)))
    Write-Host ('ETA:     {0}' -f (Format-Duration $progress.eta_seconds))
    Write-Host ('Finish:  {0}' -f $(if ($progress.estimated_completion_clock_time) { $progress.estimated_completion_clock_time } else { 'calculating' }))
    if ($state) {
        Write-Host ('State:   {0} / {1} - {2}' -f $state.status, $state.stage, $state.detail)
    }
    Write-Host ''
    Write-Host ('{0,-39} {1,-12} {2,-13} {3,-9} {4,-8} {5,-9}' -f 'PIPELINE','PHASE','CASES','AUDIO','RTF','RAM')
    $processRows = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match 'diarization-benchmark.+run-case'
    })
    foreach ($row in $progress.pipelines) {
        $cases = '{0}/{1}' -f $row.completed_cases, $row.planned_cases
        $audio = '{0:N1}%' -f [double]$row.audio_weighted_percentage
        $rtf = if ($null -eq $row.rolling_rtf) { '-' } else { '{0:N3}' -f [double]$row.rolling_rtf }
        $escapedPipeline = [Regex]::Escape([string]$row.pipeline)
        $pipelineProcess = $processRows | Where-Object { $_.CommandLine -match ("--pipeline\s+" + $escapedPipeline + "(?:\s|$)") } | Select-Object -Last 1
        $liveProcess = if ($pipelineProcess) { Get-Process -Id $pipelineProcess.ProcessId -ErrorAction SilentlyContinue } else { $null }
        $ram = if ($liveProcess) { '{0:N0} MB' -f ([double]$liveProcess.WorkingSet64 / 1MB) } elseif ($row.status -eq 'RUNNING' -and $null -ne $row.current_rss_mb) { '{0:N0} MB' -f [double]$row.current_rss_mb } else { '-' }
        Write-Host ('{0,-39} {1,-12} {2,-13} {3,-9} {4,-8} {5,-9}' -f $row.pipeline, $row.status, $cases, $audio, $rtf, $ram)
        if ($row.current_case) {
            $case = $CaseIndex[[string]$row.current_case]
            $scenario = if ($case -and $case.scenario_profile) { [string]$case.scenario_profile } elseif ($case) { ('{0}/{1}' -f $case.turn_cadence, $case.overlap_profile) } else { '-' }
            $speakers = if ($case) { [string]$case.speaker_count } else { '-' }
            $pidValue = if ($pipelineProcess) { [string]$pipelineProcess.ProcessId } else { '-' }
            $cpuValue = if ($liveProcess) { '{0:N1}s' -f [double]$liveProcess.CPU } else { '-' }
            Write-Host ('  current: {0}  scenario: {1}  speakers: {2}  PID: {3}  CPU: {4}' -f $row.current_case, $scenario, $speakers, $pidValue, $cpuValue)
        }
        $latest = Get-ChildItem -LiteralPath @(
            (Join-Path $ResultRoot ("v1\development\" + [string]$row.pipeline)),
            (Join-Path $ResultRoot ("v2\development\" + [string]$row.pipeline))
        ) -Filter summary.json -File -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latest) { Write-Host ('  latest result activity: {0}' -f $latest.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')) }
        if ($row.failed_cases -gt 0 -or $row.last_error) { Write-Warning ('{0}: failures={1}; {2}' -f $row.pipeline, $row.failed_cases, $row.last_error) }
    }
    Write-Host ''
    Write-Host ('PID: {0}  Updated: {1}' -f $progress.current_process_pid, $progress.updated_timestamp)
    Write-Host 'Ctrl+C closes only this read-only monitor.'
}

do {
    Show-Progress
    if (-not $Follow) { break }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
