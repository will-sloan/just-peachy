[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Plan', 'Validate', 'Run', 'Status', 'Collect')]
    [string]$Action = 'Plan',
    [string[]]$Backends = @(),
    [string]$ProtocolRoot = '',
    [string]$ResultBase = '',
    [string]$CollectRoot = '',
    [string]$ManagementPython = '',
    [ValidateRange(1, 16)]
    [int]$EvaluationWorkers = 6
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
if (-not $ProtocolRoot) {
    $ProtocolRoot = Join-Path $ToolRoot 'benchmarks\speaker_breadth\commonvoice_60plus_v1'
}
if (-not $ManagementPython) {
    $ManagementPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $ManagementPython -PathType Leaf)) {
    throw "Management Python is missing: $ManagementPython"
}
if (-not $ResultBase) {
    if ($env:JP_SPEAKER_BREADTH_RESULT_ROOT) {
        $ResultBase = $env:JP_SPEAKER_BREADTH_RESULT_ROOT
    }
    else {
        $ResultBase = Join-Path $ToolRoot 'JustPeachyResults\speaker_breadth\commonvoice_60plus_v1'
    }
}

function Invoke-Management {
    param([string[]]$Arguments)
    & $ManagementPython $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Evaluation management command failed with exit code $LASTEXITCODE"
    }
}

function Get-ProtocolSummary {
    $Path = Join-Path $ProtocolRoot 'protocol_summary.json'
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Frozen protocol is missing. Run -Action Prepare first: $ProtocolRoot"
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Test-ValidResult {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath (Join-Path $Path 'protocol_run.json') -PathType Leaf)) {
        return $false
    }
    & $ManagementPython $Launcher speaker-protocol validate --result-root $Path *> $null
    return $LASTEXITCODE -eq 0
}

function Test-ValidExtraction {
    param([string]$Path, [string]$Backend)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    & $ManagementPython $Launcher speaker-breadth validate-extraction --protocol-root $ProtocolRoot --extraction-root $Path --backend $Backend *> $null
    return $LASTEXITCODE -eq 0
}

function Get-BackendRuntime {
    param([string]$Backend)
    $Text = & $ManagementPython $Launcher speaker-breadth backend-runtime --backend $Backend
    if ($LASTEXITCODE -ne 0) {
        throw "Could not resolve qualified runtime for backend: $Backend"
    }
    return ($Text | Out-String | ConvertFrom-Json)
}

function Require-Backends {
    if ($Backends.Count -eq 0) {
        throw "Action $Action requires -Backends with one or more Stage 10 finalist IDs."
    }
}

switch ($Action) {
    'Prepare' {
        Invoke-Management @('speaker-breadth', 'prepare', '--protocol-root', $ProtocolRoot)
    }
    'Plan' {
        $Arguments = @('speaker-breadth', 'plan', '--protocol-root', $ProtocolRoot)
        foreach ($Backend in $Backends) {
            $Arguments += @('--backend', $Backend)
        }
        Invoke-Management $Arguments
        Write-Output "Evaluation workers: $EvaluationWorkers"
    }
    'Validate' {
        Invoke-Management @('speaker-breadth', 'validate', '--protocol-root', $ProtocolRoot, '--verify-audio-hashes')
    }
    'Status' {
        Require-Backends
        $Summary = Get-ProtocolSummary
        Write-Output "Protocol: $($Summary.protocol_id)"
        Write-Output "Protocol artifacts: $ProtocolRoot"
        Write-Output "Evaluation workers: $EvaluationWorkers"
        Write-Output ('{0,-42} {1,-24} {2,-12} {3,-10} {4,-10} {5}' -f 'BACKEND', 'STATUS', 'PROGRESS', 'ELAPSED', 'RATE', 'ETA')
        foreach ($Backend in $Backends) {
            $BackendRoot = Join-Path (Join-Path $ResultBase $Summary.protocol_id) $Backend
            $ExtractionRoot = Join-Path $BackendRoot 'extraction'
            $ResultRoot = Join-Path $BackendRoot 'result'
            $ProgressPath = Join-Path $ResultRoot 'evaluation_progress.json'
            $ProgressText = '-'
            $ElapsedText = '-'
            $RateText = '-'
            $EtaText = '-'
            if (Test-ValidResult $ResultRoot) {
                $Status = 'VALID'
            }
            elseif (Test-Path -LiteralPath (Join-Path $ResultRoot 'protocol_run.json') -PathType Leaf) {
                $Status = 'INVALID'
            }
            elseif (Test-Path -LiteralPath $ProgressPath -PathType Leaf) {
                try {
                    $Progress = Get-Content -LiteralPath $ProgressPath -Raw | ConvertFrom-Json
                    $Status = if ($Progress.status -eq 'FAILED') { 'PARTIAL:FAILED' } else { "EVALUATING:$($Progress.phase)" }
                    if ($null -ne $Progress.bootstrap_total) {
                        $ProgressText = "$($Progress.bootstrap_completed)/$($Progress.bootstrap_total)"
                    }
                    $ElapsedText = [TimeSpan]::FromSeconds([double]$Progress.elapsed_sec).ToString('hh\:mm\:ss')
                    if ($null -ne $Progress.bootstrap_per_second) { $RateText = ('{0:N2}/s' -f [double]$Progress.bootstrap_per_second) }
                    if ($null -ne $Progress.estimated_remaining_sec) { $EtaText = [TimeSpan]::FromSeconds([double]$Progress.estimated_remaining_sec).ToString('hh\:mm\:ss') }
                }
                catch { $Status = 'PARTIAL' }
            }
            elseif (Test-ValidExtraction $ExtractionRoot $Backend) {
                $Status = 'EXTRACTION_COMPLETE'
            }
            elseif (Test-Path -LiteralPath $ExtractionRoot -PathType Container) {
                $Status = 'EXTRACTING'
            }
            elseif (Test-Path -LiteralPath $BackendRoot) {
                $Status = 'PARTIAL'
            }
            else {
                $Status = 'NOT_RUN'
            }
            Write-Output ('{0,-42} {1,-24} {2,-12} {3,-10} {4,-10} {5}' -f $Backend, $Status, $ProgressText, $ElapsedText, $RateText, $EtaText)
        }
    }
    'Run' {
        Require-Backends
        Invoke-Management @('speaker-breadth', 'validate', '--protocol-root', $ProtocolRoot, '--verify-audio-hashes')
        $Summary = Get-ProtocolSummary
        foreach ($Backend in $Backends) {
            $Runtime = Get-BackendRuntime $Backend
            $BackendRoot = Join-Path (Join-Path $ResultBase $Summary.protocol_id) $Backend
            $ExtractionRoot = Join-Path $BackendRoot 'extraction'
            $ResultRoot = Join-Path $BackendRoot 'result'
            New-Item -ItemType Directory -Force -Path $BackendRoot | Out-Null
            if (Test-ValidResult $ResultRoot) {
                Write-Output "[REUSE] $Backend"
                continue
            }
            if (Test-ValidExtraction $ExtractionRoot $Backend) {
                Write-Output "[REUSE EXTRACTION] $Backend"
            }
            else {
                Write-Output "[EXTRACT] $Backend using $($Runtime.environment_profile)"
                & $Runtime.python $Launcher speaker-protocol extract --manifest-root $ProtocolRoot --component $Backend --output-root $ExtractionRoot
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "[FAIL] extraction failed for $Backend"
                    continue
                }
                if (-not (Test-ValidExtraction $ExtractionRoot $Backend)) {
                    Write-Warning "[FAIL] extraction bundle is invalid for $Backend"
                    continue
                }
            }
            if (Test-Path -LiteralPath $ResultRoot) {
                $Label = if (Test-Path -LiteralPath (Join-Path $ResultRoot 'protocol_run.json') -PathType Leaf) { 'invalid' } else { 'partial' }
                $Quarantine = "$ResultRoot.$Label-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
                Move-Item -LiteralPath $ResultRoot -Destination $Quarantine
                Write-Output "[PRESERVE PARTIAL] $Quarantine"
            }
            Write-Output "[EVALUATE] $Backend workers=$EvaluationWorkers"
            $ThreadVariables = @('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS')
            $PriorThreadValues = @{}
            foreach ($Name in $ThreadVariables) {
                $PriorThreadValues[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process')
                [Environment]::SetEnvironmentVariable($Name, '1', 'Process')
            }
            try {
                & $ManagementPython $Launcher speaker-protocol evaluate --manifest-root $ProtocolRoot --observation-bundle (Join-Path $ExtractionRoot 'observations.npz') --backend-identity (Join-Path $ExtractionRoot 'backend_identity.json') --output-root $ResultRoot --workers $EvaluationWorkers
            }
            finally {
                foreach ($Name in $ThreadVariables) { [Environment]::SetEnvironmentVariable($Name, $PriorThreadValues[$Name], 'Process') }
            }
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "[FAIL] evaluation failed for $Backend"
                continue
            }
            Write-Output "[VALIDATE] $Backend"
            if (Test-ValidResult $ResultRoot) {
                Write-Output "[PASS] $Backend"
            }
            else {
                Write-Warning "[FAIL] result validation failed for $Backend"
            }
        }
    }
    'Collect' {
        Require-Backends
        $Summary = Get-ProtocolSummary
        if (-not $CollectRoot) {
            $CollectRoot = Join-Path $ToolRoot "JustPeachyResearchSummaries\speaker_breadth_commonvoice_60plus_$($Summary.protocol_id)"
        }
        $Arguments = @('speaker-breadth', 'collect', '--protocol-root', $ProtocolRoot, '--result-base', $ResultBase, '--output-root', $CollectRoot)
        foreach ($Backend in $Backends) {
            $Arguments += @('--backend', $Backend)
        }
        Invoke-Management $Arguments
    }
}
