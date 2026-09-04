[CmdletBinding()]
param(
    [switch]$Follow,
    [ValidateRange(2,3600)]
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ResultRoot = Join-Path $ToolRoot 'JustPeachyResults\hybrid_speaker_attribution_product_v2_development'
$ProgressPath = Join-Path $ResultRoot 'campaign_progress.json'
$StatePath = Join-Path $ResultRoot 'controller_state.json'

function Format-Bar([double]$Percent, [int]$Width = 28) {
    $bounded = [Math]::Max(0, [Math]::Min(100, $Percent))
    $filled = [int][Math]::Round($bounded * $Width / 100)
    return '[' + ('#' * $filled) + ('-' * ($Width - $filled)) + ('] {0,6:N1}%' -f $bounded)
}

function Format-Duration($Seconds) {
    if ($null -eq $Seconds) { return 'calculating from measured work' }
    return [TimeSpan]::FromSeconds([Math]::Max(0, [double]$Seconds)).ToString('hh\:mm\:ss')
}

function Show-HybridProgress {
    Clear-Host
    Write-Host 'JUST-PEACHY HYBRID PRODUCT V2 DEVELOPMENT'
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
    # A cache-heavy resume has no trustworthy rolling inference-rate baseline.
    # Keep ETA explicitly unset rather than extrapolating through reused work.
    $displayEta = $null
    Write-Host ('Elapsed: {0}   ETA: {1}' -f (Format-Duration $progress.elapsed_sec), (Format-Duration $displayEta))
    Write-Host ''
    Write-Host ('{0,-38} {1,-12} {2,-16} {3,-13}' -f 'IDENTITY BACKEND','STATUS','JOBS','AUDIO WORK')
    foreach ($property in $progress.embedding_backends.PSObject.Properties) {
        $row = $property.Value
        $inventorySummary = Join-Path $ResultRoot ('cache_inventory\' + $property.Name + '.jobs.summary.json')
        $expectedJobs = [int]$row.planned_jobs
        if (Test-Path -LiteralPath $inventorySummary -PathType Leaf) {
            try { $expectedJobs = [int](Get-Content -LiteralPath $inventorySummary -Raw | ConvertFrom-Json).jobs } catch { }
        }
        $backendSidecar = Join-Path $ResultRoot ('embedding_progress\' + $property.Name + '.json')
        if (Test-Path -LiteralPath $backendSidecar -PathType Leaf) {
            try {
                $candidate = Get-Content -LiteralPath $backendSidecar -Raw | ConvertFrom-Json
                if ([int]$candidate.planned_jobs -eq $expectedJobs) { $row = $candidate }
            } catch { }
        }
        if ([int]$row.planned_jobs -ne $expectedJobs) {
            $row = [pscustomobject]@{ status = 'QUEUED'; completed_jobs = 0; planned_jobs = $expectedJobs; completed_audio_sec = 0; planned_audio_sec = 1 }
        }
        $jobs = '{0}/{1}' -f $row.completed_jobs, $row.planned_jobs
        $audioPercent = if ([double]$row.planned_audio_sec -gt 0) { 100 * [double]$row.completed_audio_sec / [double]$row.planned_audio_sec } else { 0 }
        Write-Host ('{0,-38} {1,-12} {2,-16} {3,10:N1}%' -f $property.Name, $row.status, $jobs, $audioPercent)
    }
    Write-Host ''
    $liveScoreBundles = @(Get-ChildItem -LiteralPath (Join-Path $ResultRoot 'score_bundles') -Filter '*.json.gz' -File -Recurse -ErrorAction SilentlyContinue).Count
    Write-Host ('Score bundles: {0}/{1}' -f $liveScoreBundles, $progress.score_bundles.planned)
    Write-Host ('Policy replay: {0}/{1}' -f $progress.policy_replay.completed, $progress.policy_replay.planned)
    $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'hybrid-product-v2|hybrid_speaker_attribution.embedding_cache' })
    if ($processes) {
        Write-Host ('Active scientific processes: {0}' -f (($processes.ProcessId | Sort-Object) -join ', '))
    }
    $latest = Get-ChildItem -LiteralPath $ResultRoot -File -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) { Write-Host ('Latest output activity: {0}  {1}' -f $latest.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'), $latest.FullName) }
    Write-Host 'Ctrl+C closes only this read-only monitor.'
}

do {
    Show-HybridProgress
    if (-not $Follow) { break }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
