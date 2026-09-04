[CmdletBinding()]
param(
    [switch]$Follow,
    [ValidateRange(2,3600)]
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ProgressPath = Join-Path $ToolRoot 'JustPeachyResults\diarization_finalists_final_evaluation\campaign_progress.json'
$StatePath = Join-Path $ToolRoot 'JustPeachyResults\diarization_finalists_final_evaluation\controller_state.json'

function Format-Duration([Nullable[double]]$Seconds) {
    if ($null -eq $Seconds) { return 'calculating' }
    return [TimeSpan]::FromSeconds([Math]::Max(0, $Seconds)).ToString('hh\:mm\:ss')
}

function Format-Bar([double]$Percent, [int]$Width = 28) {
    $bounded = [Math]::Max(0, [Math]::Min(100, $Percent))
    $filled = [int][Math]::Round($bounded * $Width / 100)
    return '[' + ('#' * $filled) + ('-' * ($Width - $filled)) + ('] {0,6:N1}%' -f $bounded)
}

function Show-FinalProgress {
    Clear-Host
    Write-Host 'JUST-PEACHY FROZEN FINAL DIARIZATION EVALUATION'
    Write-Host ''
    if (-not (Test-Path -LiteralPath $ProgressPath)) {
        Write-Host "Progress has not started: $ProgressPath"
        return
    }
    $p = Get-Content -LiteralPath $ProgressPath -Raw | ConvertFrom-Json
    $state = if (Test-Path -LiteralPath $StatePath) { Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json } else { $null }
    Write-Host ('OVERALL: ' + (Format-Bar ([double]$p.overall_audio_weighted_percentage)))
    Write-Host ("PHASE: {0}" -f $p.phase)
    Write-Host ("Units: {0} / {1}   Failures: {2}" -f $p.completed_units, $p.planned_units, $p.failed_units)
    Write-Host ("Elapsed: {0}   ETA: {1}" -f (Format-Duration $p.elapsed_seconds), (Format-Duration $p.eta_seconds))
    $completion = if ($null -eq $p.estimated_completion_clock_time) { 'calculating' } else { $p.estimated_completion_clock_time }
    Write-Host ("Estimated completion: {0}" -f $completion)
    $cpuText = if ($null -eq $p.current_cpu_percent) { 'n/a' } else { '{0:N1}%' -f $p.current_cpu_percent }
    $ramText = if ($null -eq $p.current_rss_mb) { 'n/a' } else { '{0:N0} MB' -f $p.current_rss_mb }
    Write-Host ("CPU: {0}   RAM: {1}" -f $cpuText, $ramText)
    if ($state) { Write-Host ("Controller: {0} - {1}" -f $state.status, $state.detail) }
    Write-Host ''
    foreach ($row in $p.pipelines) {
        Write-Host ("{0} | {1}" -f $row.phase, $row.pipeline)
        Write-Host ('  ' + (Format-Bar ([double]$row.audio_weighted_percentage) 22))
        $currentText = if ($null -eq $row.current_case) { '-' } else { $row.current_case }
        $rtfText = if ($null -eq $row.rolling_rtf) { 'calculating' } else { '{0:N3}' -f $row.rolling_rtf }
        $peakText = if ($null -eq $row.peak_ram_mb) { 'n/a' } else { '{0:N0} MB' -f $row.peak_ram_mb }
        Write-Host ("  Case: {0}/{1}  Current: {2}  RTF: {3}  Peak RAM: {4}  Failures: {5}" -f `
            $row.completed_cases, $row.planned_cases, $currentText, $rtfText, $peakText, $row.failed_cases)
    }
    Write-Host ''
    Write-Host 'Ctrl+C closes this read-only monitor only.'
}

do {
    Show-FinalProgress
    if (-not $Follow) { break }
    $p = if (Test-Path -LiteralPath $ProgressPath) { Get-Content -LiteralPath $ProgressPath -Raw | ConvertFrom-Json } else { $null }
    if ($p -and $p.status -in @('COMPLETE','FAILED','STOPPED')) { break }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
