[CmdletBinding()]
param(
    [switch]$Follow,
    [ValidateRange(2,3600)]
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ResultRoot = Join-Path $ToolRoot 'JustPeachyResults\hybrid_speaker_attribution_product_v2_final_evaluation'
$ProgressPath = Join-Path $ResultRoot 'campaign_progress.json'
$StatePath = Join-Path $ResultRoot 'controller_state.json'

function Format-Bar([double]$Percent, [int]$Width = 30) {
    $bounded = [Math]::Max(0, [Math]::Min(100, $Percent))
    $filled = [int][Math]::Round($bounded * $Width / 100)
    return '[' + ('#' * $filled) + ('-' * ($Width - $filled)) + ('] {0,6:N1}%' -f $bounded)
}

function Format-Duration($Seconds) {
    if ($null -eq $Seconds) { return 'calculating from measured work' }
    return [TimeSpan]::FromSeconds([Math]::Max(0, [double]$Seconds)).ToString('dd\.hh\:mm\:ss')
}

function Show-FinalHybridProgress {
    Clear-Host
    Write-Host 'HYBRID FINAL EVALUATION'
    Write-Host ''
    if (-not (Test-Path -LiteralPath $ProgressPath -PathType Leaf)) {
        Write-Host "Progress has not started: $ProgressPath"
        return
    }
    try { $progress = Get-Content -LiteralPath $ProgressPath -Raw | ConvertFrom-Json } catch { Write-Host 'Atomic progress refresh in flight; retrying.'; return }
    $state = $null
    if (Test-Path -LiteralPath $StatePath -PathType Leaf) { try { $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json } catch { } }
    Write-Host (Format-Bar ([double]$progress.overall_percent))
    if ($state) { Write-Host ('State: {0} / {1} - {2}' -f $state.status, $state.stage, $state.detail) }
    Write-Host ('Scope: {0}   Finalist: {1}   Case: {2}' -f $progress.current_scope, $progress.current_finalist, $progress.current_case)
    Write-Host ('Overlay: {0}   Gallery: {1}' -f $progress.overlay, $progress.gallery_size)
    Write-Host ('Elapsed: {0}   ETA: {1}' -f (Format-Duration $progress.elapsed_sec), (Format-Duration $progress.eta_sec))
    if ($null -ne $progress.eta_sec) { Write-Host ('Estimated finish: {0}' -f (Get-Date).AddSeconds([double]$progress.eta_sec).ToString('yyyy-MM-dd HH:mm:ss')) }
    Write-Host ''
    foreach ($property in $progress.embedding_backends.PSObject.Properties) {
        $row = $property.Value
        $sidecar = Join-Path $ResultRoot ('embedding_progress\' + $property.Name + '.json')
        if (Test-Path -LiteralPath $sidecar -PathType Leaf) { try { $row = Get-Content -LiteralPath $sidecar -Raw | ConvertFrom-Json } catch { } }
        $percent = if ([double]$row.planned_audio_sec -gt 0) { 100 * [double]$row.completed_audio_sec / [double]$row.planned_audio_sec } else { 0 }
        Write-Host ('{0,-38} {1,-10} {2,7}/{3,-7} {4,6:N1}%' -f $property.Name, $row.status, $row.completed_jobs, $row.planned_jobs, $percent)
    }
    Write-Host ('Score bundles: {0}/{1}' -f $progress.score_bundles.completed, $progress.score_bundles.planned)
    Write-Host ('Frozen policy replay: {0}/{1}' -f $progress.policy_replay.completed, $progress.policy_replay.planned)
    Write-Host ('Cache reuse: {0}   Failures: {1}   Warnings: {2}' -f $progress.cache_reuse, $progress.failures, $progress.warnings)
    $processRows = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'hybrid-final-evaluation|hybrid_final_evaluation|hybrid_speaker_attribution.embedding_cache' })
    if ($processRows) {
        $pids = @($processRows.ProcessId)
        $processes = @(Get-Process -Id $pids -ErrorAction SilentlyContinue)
        $ram = ($processes | Measure-Object WorkingSet64 -Sum).Sum / 1MB
        $cpuTime = ($processes | Measure-Object CPU -Sum).Sum
        Write-Host ('Active PIDs: {0}   CPU time: {1:N1}s   RAM: {2:N1} MB' -f (($pids | Sort-Object) -join ', '), $cpuTime, $ram)
    }
    $completedAudio = 0.0
    foreach ($property in $progress.embedding_backends.PSObject.Properties) { $completedAudio += [double]$property.Value.completed_audio_sec }
    if ($completedAudio -gt 0 -and $progress.elapsed_sec) { Write-Host ('Measured controller-wall/audio-work ratio: {0:N3}' -f ([double]$progress.elapsed_sec / $completedAudio)) }
    $latest = Get-ChildItem -LiteralPath $ResultRoot -File -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) { Write-Host ('Latest output activity: {0}  {1}' -f $latest.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'), $latest.FullName) }
    Write-Host 'Ctrl+C closes only this read-only monitor.'
}

do {
    Show-FinalHybridProgress
    if (-not $Follow) { break }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)

