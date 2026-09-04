[CmdletBinding()]
param(
    [string]$WorkspaceRoot,
    [switch]$Follow,
    [ValidateRange(2,3600)]
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_speech_pipeline_v1'
}
$ProgressPath = Join-Path $WorkspaceRoot 'campaign_progress.json'
$StatePath = Join-Path $WorkspaceRoot 'controller_state.json'

function Format-Duration([Nullable[double]]$Seconds) {
    if ($null -eq $Seconds) { return 'calculating' }
    return [TimeSpan]::FromSeconds([Math]::Max(0, $Seconds)).ToString('d\.hh\:mm\:ss')
}

function Format-Bar([double]$Percent, [int]$Width = 28) {
    $bounded = [Math]::Max(0, [Math]::Min(100, $Percent))
    $filled = [int][Math]::Round($bounded * $Width / 100)
    return '[' + ('#' * $filled) + ('-' * ($Width - $filled)) + ('] {0,6:N1}%' -f $bounded)
}

function Format-Optional([object]$Value, [string]$Pattern = '{0}') {
    if ($null -eq $Value) { return 'n/a' }
    return ($Pattern -f $Value)
}

function Show-EvaluationProgress {
    Clear-Host
    Write-Host 'JUST-PEACHY FULL-PIPELINE V1 EVALUATION'
    Write-Host ''
    if (-not (Test-Path -LiteralPath $ProgressPath -PathType Leaf)) {
        Write-Host "Progress is not prepared: $ProgressPath"
        return $null
    }
    $p = Get-Content -LiteralPath $ProgressPath -Raw | ConvertFrom-Json
    $state = if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
        Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    } else { $null }
    Write-Host ('OVERALL ' + (Format-Bar ([double]$p.overall_percentage)))
    Write-Host ("Status/phase: {0} / {1}" -f $p.status, $p.phase)
    Write-Host ("Pipeline: {0}   Protocol: {1}" -f $p.current_pipeline_id, $p.current_protocol_id)
    Write-Host ("Case: {0}   Cases: {1}/{2}   Jobs: {3}/{4}" -f `
        $p.current_case_id, $p.completed_cases, $p.planned_cases, $p.complete_jobs, $p.planned_jobs)
    Write-Host ("Audio: {0:N1}/{1:N1} sec   Elapsed: {2}   ETA: {3}" -f `
        $p.completed_audio_sec, $p.planned_audio_sec,
        (Format-Duration $p.elapsed_sec), (Format-Duration $p.eta_sec))
    $finish = if ($null -eq $p.estimated_finish_utc) { 'calculating' } else { $p.estimated_finish_utc }
    Write-Host ("Current/estimated finish: {0} / {1}" -f $p.updated_at_utc, $finish)
    Write-Host ("RTF: {0}   CPU: {1}   RAM: {2}   Queue: {3}" -f `
        (Format-Optional $p.rolling_rtf '{0:N3}'),
        (Format-Optional $p.current_cpu_percent '{0:N1}%'),
        (Format-Optional $p.current_rss_mb '{0:N0} MB'),
        (Format-Optional $p.current_queue_depth '{0}'))
    Write-Host ("Cache hits: {0}   Failures: {1}   Retries: {2}" -f `
        $p.cache_hits, $p.failures, $p.retries)
    Write-Host ("Latest activity: {0}" -f $p.latest_activity)
    if ($state) { Write-Host ("Controller: {0} — {1}" -f $state.status, $state.detail) }
    Write-Host ''
    foreach ($job in @($p.jobs | Where-Object { $_.state -in @('running','failed','partial') } | Select-Object -First 8)) {
        Write-Host ("{0} | {1} | {2} | {3}" -f $job.pipeline_id, $job.protocol_id, $job.measurement_mode, $job.state)
        Write-Host ('  ' + (Format-Bar ([double]$job.percentage) 20))
        Write-Host ("  case {0}/{1}; audio {2:N1}/{3:N1}s; current {4}" -f `
            $job.completed_cases, $job.planned_cases, $job.completed_audio_sec,
            $job.planned_audio_sec, $job.current_case_id)
    }
    Write-Host ''
    Write-Host 'Ctrl+C closes this read-only monitor; it does not stop evaluation.'
    return $p
}

do {
    $progress = Show-EvaluationProgress
    if (-not $Follow) { break }
    if ($progress -and $progress.status -in @('COMPLETE','FAILED','STOPPED')) { break }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
