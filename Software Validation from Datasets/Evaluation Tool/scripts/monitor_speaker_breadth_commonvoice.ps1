[CmdletBinding()]
param(
    [string]$ProtocolRoot = '',
    [string]$ResultBase = '',
    [int]$RefreshSeconds = 30,
    [int]$EvaluationWorkers = 6,
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $ProtocolRoot) { $ProtocolRoot = Join-Path $ToolRoot 'benchmarks\speaker_breadth\commonvoice_60plus_v1' }
if (-not $ResultBase) { $ResultBase = Join-Path $ToolRoot 'JustPeachyResults\speaker_breadth\commonvoice_60plus_v1' }
$Protocol = Get-Content -LiteralPath (Join-Path $ProtocolRoot 'protocol_summary.json') -Raw | ConvertFrom-Json
$Backends = @(
    'speechbrain_ecapa',
    'resemblyzer',
    'wespeaker',
    'eres2net_base_speaker_embedding',
    'redimnet2_b2_speaker_embedding'
)

function Format-Duration([object]$Seconds) {
    if ($null -eq $Seconds) { return '-' }
    return [TimeSpan]::FromSeconds([double]$Seconds).ToString('hh\:mm\:ss')
}

do {
    try { Clear-Host } catch { }
    Write-Output 'COMMON VOICE 60+ FIVE-MODEL RUN'
    Write-Output "Current time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Output "Protocol: $($Protocol.protocol_id)"
    Write-Output "Evaluation workers: $EvaluationWorkers"
    Write-Output ''
    Write-Output ('{0,-42} {1,-12} {2,-22} {3,-12} {4,-10} {5,-10} {6}' -f 'BACKEND','STATE','PHASE','PROGRESS','ELAPSED','RATE','ETA')
    foreach ($Backend in $Backends) {
        $Root = Join-Path (Join-Path (Join-Path $ResultBase $Protocol.protocol_id) $Backend) 'result'
        $Extraction = Join-Path (Split-Path $Root -Parent) 'extraction'
        $ProgressPath = Join-Path $Root 'evaluation_progress.json'
        $State = 'NOT_RUN'; $Phase = '-'; $Done = '-'; $Elapsed = '-'; $Rate = '-'; $Eta = '-'
        if (Test-Path -LiteralPath (Join-Path $Root 'protocol_run.json') -PathType Leaf) {
            $State = 'RESULT'; $Phase = 'COMPLETE'
        }
        elseif (Test-Path -LiteralPath $ProgressPath -PathType Leaf) {
            try {
                $Progress = Get-Content -LiteralPath $ProgressPath -Raw | ConvertFrom-Json
                $State = if ($Progress.status -eq 'FAILED') { 'PARTIAL' } else { 'RUNNING' }
                $Phase = [string]$Progress.phase
                if ($null -ne $Progress.bootstrap_total) { $Done = "$($Progress.bootstrap_completed)/$($Progress.bootstrap_total)" }
                $Elapsed = Format-Duration $Progress.elapsed_sec
                if ($null -ne $Progress.bootstrap_per_second) { $Rate = ('{0:N2}/s' -f [double]$Progress.bootstrap_per_second) }
                $Eta = Format-Duration $Progress.estimated_remaining_sec
            }
            catch { $State = 'PARTIAL'; $Phase = 'UNREADABLE_PROGRESS' }
        }
        elseif ((Test-Path -LiteralPath (Join-Path $Extraction 'observations.npz') -PathType Leaf) -and (Test-Path -LiteralPath (Join-Path $Extraction 'backend_identity.json') -PathType Leaf) -and (Test-Path -LiteralPath (Join-Path $Extraction 'extraction_summary.json') -PathType Leaf)) {
            $State = 'READY'; $Phase = 'EXTRACTION_COMPLETE'
        }
        elseif (Test-Path -LiteralPath $Extraction -PathType Container) { $State = 'RUNNING'; $Phase = 'EXTRACTING' }
        elseif (Test-Path -LiteralPath $Root -PathType Container) { $State = 'PARTIAL' }
        Write-Output ('{0,-42} {1,-12} {2,-22} {3,-12} {4,-10} {5,-10} {6}' -f $Backend,$State,$Phase,$Done,$Elapsed,$Rate,$Eta)
    }

    $Active = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -like '*speaker-protocol*evaluate*' -or $_.CommandLine -like "*$($Protocol.protocol_id)*") -and $_.ProcessId -ne $PID }
    Write-Output ''
    Write-Output 'ACTIVE PROCESS:'
    if ($Active) {
        $CpuSamples = @{}
        Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -ErrorAction SilentlyContinue | ForEach-Object {
            $CpuSamples[[int]$_.IDProcess] = [double]$_.PercentProcessorTime
        }
        foreach ($Item in $Active) {
            $Process = Get-Process -Id $Item.ProcessId -ErrorAction SilentlyContinue
            if ($Process) {
                $CpuPercent = if ($CpuSamples.ContainsKey([int]$Process.Id)) { [math]::Round($CpuSamples[[int]$Process.Id], 1) } else { '-' }
                Write-Output "PID=$($Process.Id) CPU_PERCENT=$CpuPercent CPU_SEC=$([math]::Round($Process.CPU,1)) RAM_MB=$([math]::Round($Process.WorkingSet64/1MB,1))"
            }
        }
    }
    else { Write-Output '-' }

    $Latest = Get-ChildItem -LiteralPath (Join-Path $ResultBase $Protocol.protocol_id) -Recurse -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Write-Output ''
    Write-Output 'LATEST RESULT ACTIVITY:'
    if ($Latest) { Write-Output "$($Latest.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))  $($Latest.FullName)" } else { Write-Output '-' }
    if (-not $Once) { Start-Sleep -Seconds $RefreshSeconds }
} while (-not $Once)
